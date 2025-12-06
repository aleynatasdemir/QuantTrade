"""
Pydantic models for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# Portfolio Models
class PendingBuy(BaseModel):
    symbol: str
    planned_capital: float
    decision_date: str


class Position(BaseModel):
    """Portfolio position model"""
    symbol: str
    entry_price: float
    shares: int
    entry_date: str
    days_held: int
    # Frontend compatibility fields
    avg_price: Optional[float] = None
    current_price: Optional[float] = None


class PortfolioState(BaseModel):
    cash: float
    positions: List[Position]
    pending_buys: List[PendingBuy]
    last_date: Optional[str]


class EquityPoint(BaseModel):
    date: str
    equity: float
    cash: float
    portfolio_value: float
    daily_return: float
    n_positions: int


class Trade(BaseModel):
    entry_date: str
    exit_date: str
    symbol: str
    entry_price: float
    exit_price: Optional[float]
    shares: int
    return_pct: Optional[float] = Field(alias="return")
    reason: str
    days_held: int


# Pipeline Models
class PipelineStatus(BaseModel):
    status: Literal["idle", "running", "completed", "failed"]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[str] = None


class PipelineRunRequest(BaseModel):
    script: Literal["pipeline", "portfolio_manager"] = "pipeline"


class PipelineRunResponse(BaseModel):
    message: str
    status: str
    job_id: Optional[str] = None


# Telegram Models
class TelegramConfig(BaseModel):
    bot_token: str
    bot_username: str
    test_mode: bool = True


class TelegramConfigUpdate(BaseModel):
    bot_token: Optional[str] = None
    bot_username: Optional[str] = None
    test_mode: Optional[bool] = None


class TelegramSubscriber(BaseModel):
    id: int
    name: str
    chat_id: str
    role: Literal["Admin", "Trader", "Viewer"] = "Trader"
    active: bool = True
    avatar_color: str = "bg-cyan-600"


class TelegramSubscriberCreate(BaseModel):
    name: str
    chat_id: str
    role: Literal["Admin", "Trader", "Viewer"] = "Trader"


class TelegramSubscriberUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    role: Optional[Literal["Admin", "Trader", "Viewer"]] = None


class BroadcastMessage(BaseModel):
    message: str
    message_type: Literal["BUY", "SELL", "INFO"] = "INFO"
    symbol: Optional[str] = None
    price: Optional[float] = None


class TelegramMessage(BaseModel):
    id: int
    type: Literal["BUY", "SELL", "INFO"]
    symbol: str
    price: float
    timestamp: str
    date: str
    message: str
    status: Literal["SENT", "PENDING"]
