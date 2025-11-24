"""
Backend Configuration Management
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_bot_username: str = "@quant_alpha_bot"
    
    # Backend Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:3001"
    
    # Project Paths
    project_root: str = ".."
    live_state_path: str = "src/quanttrade/models_2.0/live_state_T1.json"
    live_equity_path: str = "src/quanttrade/models_2.0/live_equity_T1.csv"
    live_trades_path: str = "src/quanttrade/models_2.0/live_trades_T1.csv"
    run_pipeline_script: str = "run_daily_pipeline.py"
    live_portfolio_script: str = "src/quanttrade/models_2.0/live_portfolio_manager.py"
    
    # Telegram Subscribers
    subscribers_db_path: str = "backend/data/subscribers.json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path to absolute path from project root"""
        backend_dir = Path(__file__).parent
        project_root_dir = backend_dir / self.project_root
        return (project_root_dir / relative_path).resolve()


# Global settings instance
settings = Settings()
