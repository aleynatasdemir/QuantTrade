"""
Pipeline Service - Execute and monitor pipeline scripts
"""
import subprocess
import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from backend.config import settings
from backend.models.schemas import PipelineStatus


class PipelineService:
    """Service for executing and monitoring pipeline scripts"""
    
    def __init__(self):
        self.project_root = settings.get_absolute_path("")
        self.pipeline_script = self.project_root / settings.run_pipeline_script
        self.portfolio_script = self.project_root / settings.live_portfolio_script
        
        # Track running processes
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.status: PipelineStatus = PipelineStatus(status="idle")
        self.logs: list = []
    
    async def run_pipeline(self, script_type: str = "pipeline") -> Dict[str, str]:
        """Execute pipeline script asynchronously"""
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
        
        # Update status
        self.status = PipelineStatus(
            status="running",
            started_at=datetime.now().isoformat(),
            progress=f"Starting {script_type}..."
        )
        self.logs = []
        
        # Start the process
        try:
            # Run in project root directory
            self.current_process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Start monitoring in background
            asyncio.create_task(self._monitor_process())
            
            return {
                "status": "started",
                "message": f"{script_type} execution started",
                "job_id": str(self.current_process.pid)
            }
        except Exception as e:
            self.status = PipelineStatus(
                status="failed",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
            return {
                "status": "error",
                "message": f"Failed to start pipeline: {str(e)}"
            }
    
    async def _monitor_process(self):
        """Monitor the running process and capture output"""
        if self.current_process is None:
            return
        
        try:
            # Read output
            stdout, stderr = await self.current_process.communicate()
            
            # Store logs
            if stdout:
                self.logs.append(stdout.decode('utf-8'))
            if stderr:
                self.logs.append(stderr.decode('utf-8'))
            
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
            self.current_process = None
    
    def get_status(self) -> PipelineStatus:
        """Get current pipeline status"""
        return self.status
    
    def get_logs(self, max_lines: int = 100) -> str:
        """Get recent pipeline logs"""
        if not self.logs:
            return "No logs available"
        
        full_log = "\n".join(self.logs)
        lines = full_log.split("\n")
        
        # Return last N lines
        return "\n".join(lines[-max_lines:])


# Global service instance
pipeline_service = PipelineService()
