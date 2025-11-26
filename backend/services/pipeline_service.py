"""
Pipeline Service - Execute and monitor pipeline scripts with real-time logs
"""
import subprocess
import sys
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from config import settings
from models.schemas import PipelineStatus


class PipelineService:
    """Service for executing and monitoring pipeline scripts"""
    
    def __init__(self):
        self.project_root = settings.get_absolute_path("")
        self.pipeline_script = self.project_root / settings.run_pipeline_script
        self.portfolio_script = self.project_root / settings.live_portfolio_script
        
        # Track running processes
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.status: PipelineStatus = PipelineStatus(status="idle")
        self.log_file_path: Optional[Path] = None
        self.job_id: Optional[str] = None
        
        # Status persistence
        self.status_file = settings.get_absolute_path("backend/data/pipeline_status.json")
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load saved status on init
        self._load_status()
    
    def _save_status(self):
        """Save current status to file for persistence"""
        try:
            status_data = {
                "status": self.status.status,
                "started_at": self.status.started_at,
                "completed_at": self.status.completed_at,
                "progress": self.status.progress,
                "error": self.status.error,
                "job_id": self.job_id,
                "log_file_path": str(self.log_file_path) if self.log_file_path else None
            }
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            print(f"Failed to save status: {e}")
    
    def _load_status(self):
        """Load saved status from file"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r') as f:
                    data = json.load(f)
                
                self.status = PipelineStatus(
                    status=data.get("status", "idle"),
                    started_at=data.get("started_at"),
                    completed_at=data.get("completed_at"),
                    progress=data.get("progress"),
                    error=data.get("error")
                )
                self.job_id = data.get("job_id")
                
                if data.get("log_file_path"):
                    self.log_file_path = Path(data["log_file_path"])
                
                # If status was "running" but process is not running, mark as failed
                if self.status.status == "running" and self.current_process is None:
                    self.status = PipelineStatus(
                        status="failed",
                        started_at=self.status.started_at,
                        completed_at=datetime.now().isoformat(),
                        error="Process interrupted (server restart)"
                    )
                    self._save_status()
        except Exception as e:
            print(f"Failed to load status: {e}")
    
    async def run_pipeline(self, script_type: str = "pipeline") -> Dict[str, str]:
        """Execute pipeline script asynchronously with real-time logging"""
        if self.current_process is not None:
            return {
                "status": "error",
                "message": "A pipeline is already running"
            }
        
        # Determine which script to run
        if script_type == "pipeline":
            script_path = self.pipeline_script
        elif script_type == "portfolio_manager":
            script_path = self.portfolio_script
        else:
            return {
                "status": "error",
                "message": f"Unknown script type: {script_type}"
            }
        
        if not script_path.exists():
            return {
                "status": "error",
                "message": f"Script not found: {script_path}"
            }
        
        # Create temp log file (delete old one first)
        if self.log_file_path and self.log_file_path.exists():
            try:
                self.log_file_path.unlink()  # Eski log'u sil
            except Exception:
                pass
        
        temp_log = tempfile.NamedTemporaryFile(
            mode='w',
            prefix=f'pipeline_{script_type}_',
            suffix='.log',
            delete=False
        )
        self.log_file_path = Path(temp_log.name)
        temp_log.close()
        
        # Generate job ID
        self.job_id = f"{script_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Update status
        self.status = PipelineStatus(
            status="running",
            started_at=datetime.now().isoformat(),
            progress=f"Starting {script_type}..."
        )
        self._save_status()
        
        # Start the process
        try:
            # Determine working directory based on script type
            if script_type == "portfolio_manager":
                # Portfolio manager needs to run from its own directory (where models are)
                cwd = str(script_path.parent)
            else:
                # Pipeline scripts run from project root
                cwd = str(self.project_root)
            
            # Run in appropriate directory
            import os

            # Environment variables hazırla
            env = os.environ.copy()
            env['PYTHONPATH'] = '/root/Quanttrade/src:' + env.get('PYTHONPATH', '')

            self.current_process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                cwd=cwd,
                env=env,  # ← ENV EKLE
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Start monitoring in background
            asyncio.create_task(self._monitor_process())
            
            return {
                "status": "started",
                "message": f"{script_type} execution started",
                "job_id": self.job_id
            }
        except Exception as e:
            self.status = PipelineStatus(
                status="failed",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
            self._save_status()
            return {
                "status": "error",
                "message": f"Failed to start pipeline: {str(e)}"
            }
    
    async def stop_pipeline(self) -> Dict[str, str]:
        """Stop running pipeline process"""
        if self.current_process is None:
            # Force reset in case state is stuck
            self.status = PipelineStatus(status="idle")
            self._save_status()
            return {
                "status": "stopped",
                "message": "No pipeline was running (state reset)"
            }
        
        try:
            # Terminate the process
            try:
                self.current_process.terminate()
                await asyncio.wait_for(self.current_process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                # Force kill if it doesn't stop
                self.current_process.kill()
                await self.current_process.wait()
            except Exception:
                pass
            
            # Update status
            self.status = PipelineStatus(
                status="stopped",
                started_at=self.status.started_at if self.status else None,
                completed_at=datetime.now().isoformat(),
                error="Stopped by user"
            )
            self._save_status()
            
            # Clear process reference
            self.current_process = None
            self.job_id = None
            
            return {
                "status": "stopped",
                "message": "Pipeline stopped successfully"
            }
            
        except Exception as e:
            # Force cleanup even on error
            self.current_process = None
            self.job_id = None
            self.status = PipelineStatus(status="idle")
            self._save_status()
            
            return {
                "status": "error",
                "message": f"Pipeline stopped with error: {str(e)}"
            }
    
    
    async def _read_stream(self, stream, log_file):
        """Read stream line by line and write to log file"""
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                
                decoded_line = line.decode('utf-8')
                
                # Write to log file immediately
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(decoded_line)
                
                # Update progress if line contains step info
                if "STEP" in decoded_line.upper() or "Starting" in decoded_line:
                    self.status.progress = decoded_line.strip()
                    self._save_status()
        except Exception as e:
            print(f"Error reading stream: {e}")
    
    async def _monitor_process(self):
        """Monitor the running process and capture output in real-time"""
        if self.current_process is None or self.log_file_path is None:
            return
        
        try:
            # Read both stdout and stderr concurrently
            await asyncio.gather(
                self._read_stream(self.current_process.stdout, self.log_file_path),
                self._read_stream(self.current_process.stderr, self.log_file_path)
            )
            
            # Wait for process to complete
            await self.current_process.wait()
            
            # Check exit code
            if self.current_process.returncode == 0:
                self.status = PipelineStatus(
                    status="completed",
                    started_at=self.status.started_at,
                    completed_at=datetime.now().isoformat(),
                    progress="Pipeline completed successfully"
                )
            else:
                self.status = PipelineStatus(
                    status="failed",
                    started_at=self.status.started_at,
                    completed_at=datetime.now().isoformat(),
                    error=f"Process exited with code {self.current_process.returncode}"
                )
        except Exception as e:
            self.status = PipelineStatus(
                status="failed",
                started_at=self.status.started_at,
                completed_at=datetime.now().isoformat(),
                error=str(e)
            )
        finally:
            self._save_status()
            self.current_process = None
    
    def get_status(self) -> PipelineStatus:
        """Get current pipeline status"""
        return self.status
    
    def get_logs(self, since_line: int = 0) -> Dict:
        """Get logs from file starting from specific line"""
        if not self.log_file_path or not self.log_file_path.exists():
            return {
                "lines": [],
                "total_lines": 0
            }
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            # Get only new lines since last fetch
            new_lines = all_lines[since_line:]
            
            # Strip newlines
            new_lines = [line.rstrip('\n') for line in new_lines]
            
            return {
                "lines": new_lines,
                "total_lines": len(all_lines)
            }
        except Exception as e:
            # Assuming 'logger' is defined elsewhere or will be imported
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to read logs: {e}")
            return {
                "lines": [],
                "total_lines": 0
            }


# Global service instance
pipeline_service = PipelineService()
