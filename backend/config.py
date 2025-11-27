"""
Backend Configuration Management
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    database_url: str = "sqlite:///./backend/data/quanttrade.db"
    
    # API Keys (optional)
    telegram_bot_token: Optional[str] = None
    evds_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # API URLs (optional)
    backend_api_url: Optional[str] = "http://localhost:8000"
    vite_api_url: Optional[str] = None
    
    # Telegram Bot
    telegram_bot_username: str = "@quant_alpha_bot"
    telegram_chat_id: str = ""  # Default chat ID for live-telegram bot
    
    # Backend Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:3001"
    
    # File paths (relative to project root)
    project_root: str = ".."
    live_state_path: str = "src/quanttrade/models_2.0/live_state_T1.json"
    live_equity_path: str = "src/quanttrade/models_2.0/live_equity_T1.csv"
    live_trades_path: str = "src/quanttrade/models_2.0/live_trades_T1.csv"
    run_pipeline_script: str = "run_daily_prices.py"
    live_portfolio_script: str = "src/quanttrade/models_2.0/live_portfolio_v2.py"
    
    # Telegram Subscribers
    subscribers_db_path: str = "backend/data/subscribers.json"
    
    # Live Telegram Bot
    live_telegram_path: str = "live-telegram"
    daily_runner_script: str = "live-telegram/telegram_bot/daily_runner.py"
    
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
