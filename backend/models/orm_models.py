"""
SQLAlchemy ORM Models for QuantTrade Database
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="user", cascade="all, delete-orphan")


class Portfolio(Base):
    """Portfolio state model"""
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Portfolio metrics
    initial_capital = Column(Float, nullable=False)
    current_cash = Column(Float, nullable=False)
    total_equity = Column(Float, nullable=False)
    
    # Settings
    max_positions = Column(Integer, default=5)
    stop_loss_pct = Column(Float, default=-0.05)
    take_profit_pct = Column(Float, default=None)
    max_holding_days = Column(Integer, default=20)
    
    # Status
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_execution = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="portfolio", cascade="all, delete-orphan")
    signals_executed = relationship("Signal", back_populates="portfolio")


class Position(Base):
    """Current open position model"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    
    symbol = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    shares = Column(Integer, nullable=False)
    
    entry_date = Column(DateTime, nullable=False)
    days_held = Column(Integer, default=0)
    
    # Signals and reasoning
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)
    entry_reason = Column(Text, nullable=True)
    
    # P&L
    unrealized_pnl = Column(Float, nullable=True)
    unrealized_pnl_pct = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'symbol', name='uq_portfolio_symbol'),
    )
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="positions")
    signal = relationship("Signal", foreign_keys=[signal_id])


class Trade(Base):
    """Completed trade history model"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    
    symbol = Column(String(10), nullable=False)
    entry_date = Column(DateTime, nullable=False)
    exit_date = Column(DateTime, nullable=True)
    
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    shares = Column(Integer, nullable=False)
    
    # P&L
    realized_pnl = Column(Float, nullable=True)
    realized_pnl_pct = Column(Float, nullable=True)
    
    # Exit reason
    exit_reason = Column(String(50), nullable=True)  # STOP_LOSS, TIME_EXIT, PROFIT_TARGET, MANUAL
    days_held = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="trades")


class Signal(Base):
    """Trading signal model"""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=True)
    
    symbol = Column(String(10), nullable=False)
    signal_type = Column(String(20), nullable=False)  # BUY, SELL, HOLD
    signal_date = Column(DateTime, nullable=False)
    
    # Signal strength and model info
    confidence_score = Column(Float, nullable=True)  # 0-1
    model_name = Column(String(100), nullable=True)
    features_used = Column(Text, nullable=True)  # JSON string
    
    # Execution
    planned_capital = Column(Float, nullable=True)
    is_executed = Column(Boolean, default=False)
    execution_price = Column(Float, nullable=True)
    execution_date = Column(DateTime, nullable=True)
    
    # Additional info
    sector = Column(String(50), nullable=True)
    technical_reason = Column(Text, nullable=True)
    fundamental_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="signals")
    portfolio = relationship("Portfolio", back_populates="signals_executed")


class PriceData(Base):
    """Historical price data model"""
    __tablename__ = "price_data"
    
    id = Column(Integer, primary_key=True, index=True)
    
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    
    # OHLCV
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    
    # Adjusted prices
    adj_open = Column(Float, nullable=True)
    adj_high = Column(Float, nullable=True)
    adj_low = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    
    # Technical indicators
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uq_symbol_date'),
    )


class MacroData(Base):
    """Macroeconomic data model"""
    __tablename__ = "macro_data"
    
    id = Column(Integer, primary_key=True, index=True)
    
    date = Column(DateTime, nullable=False, unique=True, index=True)
    
    # Exchange rates
    usd_try = Column(Float, nullable=True)
    eur_try = Column(Float, nullable=True)
    
    # Indices
    bist100 = Column(Float, nullable=True)
    m2_money_supply = Column(Float, nullable=True)
    cpi_index = Column(Float, nullable=True)
    
    # Interest rates
    tcmb_policy_rate = Column(Float, nullable=True)
    
    # US Data
    us_cpi = Column(Float, nullable=True)
    us_unemployment = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class ExecutionLog(Base):
    """Pipeline execution logs"""
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    script_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # RUNNING, COMPLETED, FAILED
    
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    total_duration_seconds = Column(Float, nullable=True)
    
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
