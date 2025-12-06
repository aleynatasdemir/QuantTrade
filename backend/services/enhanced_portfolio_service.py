"""
Enhanced Portfolio Service with Database Integration
Manages portfolio state, positions, trades, and equity tracking via PostgreSQL
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import pandas as pd
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from models.database import get_db_context
from models.orm_models import (
    Portfolio, Position, Trade, EquityHistory, Signal
)
from models.schemas import (
    PortfolioState, Position as PositionSchema, EquityPoint, Trade as TradeSchema
)

logger = logging.getLogger(__name__)


class EnhancedPortfolioService:
    """Portfolio service with database and file-based fallback"""
    
    def __init__(self):
        self.live_state_path = os.getenv("LIVE_STATE_PATH",
                                         "src/quanttrade/models_2.0/live_state_T1.json")
        self.live_equity_path = os.getenv("LIVE_EQUITY_PATH",
                                          "src/quanttrade/models_2.0/live_equity_T1.csv")
        self.live_trades_path = os.getenv("LIVE_TRADES_PATH",
                                          "src/quanttrade/models_2.0/live_trades_T1.csv")
    
    # ==================== Database Methods ====================
    
    def get_portfolio_from_db(self, portfolio_id: int, db: Optional[Session] = None) -> Optional[Portfolio]:
        """Get portfolio from database"""
        try:
            should_close = False
            if db is None:
                db = next(get_db_context())
                should_close = True
            
            portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            
            if should_close:
                db.close()
            
            return portfolio
            
        except Exception as e:
            logger.error(f"Error fetching portfolio from DB: {str(e)}")
            return None
    
    def get_active_positions_from_db(self, portfolio_id: int) -> List[PositionSchema]:
        """Get all active positions from database"""
        try:
            with get_db_context() as db:
                positions = db.query(Position).filter(
                    Position.portfolio_id == portfolio_id
                ).all()
                
                return [
                    PositionSchema(
                        symbol=p.symbol,
                        entry_price=p.entry_price,
                        current_price=p.current_price or p.entry_price,
                        shares=p.shares,
                        entry_date=p.entry_date,
                        days_held=p.days_held,
                        unrealized_pnl=p.unrealized_pnl,
                        unrealized_pnl_pct=p.unrealized_pnl_pct,
                    )
                    for p in positions
                ]
                
        except Exception as e:
            logger.error(f"Error fetching positions from DB: {str(e)}")
            return []
    
    def get_trades_from_db(self, portfolio_id: int, limit: int = 100) -> List[TradeSchema]:
        """Get trade history from database"""
        try:
            with get_db_context() as db:
                trades = db.query(Trade).filter(
                    Trade.portfolio_id == portfolio_id
                ).order_by(desc(Trade.exit_date)).limit(limit).all()
                
                return [
                    TradeSchema(
                        entry_date=t.entry_date,
                        exit_date=t.exit_date,
                        symbol=t.symbol,
                        entry_price=t.entry_price,
                        exit_price=t.exit_price,
                        shares=t.shares,
                        realized_pnl_pct=t.realized_pnl_pct,
                        exit_reason=t.exit_reason,
                        days_held=t.days_held,
                    )
                    for t in trades
                ]
                
        except Exception as e:
            logger.error(f"Error fetching trades from DB: {str(e)}")
            return []
    
    def get_equity_history_from_db(self, portfolio_id: int, limit: int = 252) -> List[EquityPoint]:
        """Get equity history from database"""
        try:
            with get_db_context() as db:
                equity_records = db.query(EquityHistory).filter(
                    EquityHistory.portfolio_id == portfolio_id
                ).order_by(desc(EquityHistory.date)).limit(limit).all()
                
                # Reverse to get chronological order
                equity_records = list(reversed(equity_records))
                
                return [
                    EquityPoint(
                        date=eq.date.strftime("%Y-%m-%d"),
                        equity=eq.equity,
                        cash=eq.cash,
                        portfolio_value=eq.equity + eq.cash,
                        daily_return=eq.daily_return,
                        n_positions=eq.n_positions or 0,
                    )
                    for eq in equity_records
                ]
                
        except Exception as e:
            logger.error(f"Error fetching equity history from DB: {str(e)}")
            return []
    
    def create_position(self, portfolio_id: int, symbol: str, entry_price: float,
                       shares: int, entry_date: datetime, signal_id: Optional[int] = None) -> bool:
        """Create new position in database"""
        try:
            with get_db_context() as db:
                position = Position(
                    portfolio_id=portfolio_id,
                    symbol=symbol,
                    entry_price=entry_price,
                    shares=shares,
                    entry_date=entry_date,
                    signal_id=signal_id,
                    days_held=0,
                )
                db.add(position)
                db.commit()
                logger.info(f"Created position: {symbol} at {entry_price}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating position: {str(e)}")
            return False
    
    def close_position(self, portfolio_id: int, symbol: str, exit_price: float,
                      exit_date: datetime, exit_reason: str = "MANUAL") -> bool:
        """Close existing position and create trade record"""
        try:
            with get_db_context() as db:
                # Find open position
                position = db.query(Position).filter(
                    and_(
                        Position.portfolio_id == portfolio_id,
                        Position.symbol == symbol
                    )
                ).first()
                
                if not position:
                    logger.warning(f"Position not found: {symbol}")
                    return False
                
                # Calculate P&L
                realized_pnl = (exit_price - position.entry_price) * position.shares
                realized_pnl_pct = ((exit_price - position.entry_price) / position.entry_price * 100)
                days_held = (exit_date - position.entry_date).days
                
                # Create trade record
                trade = Trade(
                    portfolio_id=portfolio_id,
                    symbol=symbol,
                    entry_date=position.entry_date,
                    exit_date=exit_date,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    shares=position.shares,
                    realized_pnl=realized_pnl,
                    realized_pnl_pct=realized_pnl_pct,
                    exit_reason=exit_reason,
                    days_held=days_held,
                )
                db.add(trade)
                
                # Delete position
                db.delete(position)
                db.commit()
                
                logger.info(f"Closed position: {symbol} at {exit_price}, P&L: {realized_pnl:.2f} ({realized_pnl_pct:.2f}%)")
                return True
                
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}")
            return False
    
    def record_equity_snapshot(self, portfolio_id: int, date: datetime, equity: float,
                              cash: float, daily_return: float = 0.0, n_positions: int = 0) -> bool:
        """Record daily equity snapshot"""
        try:
            with get_db_context() as db:
                # Check if record already exists for this date
                existing = db.query(EquityHistory).filter(
                    and_(
                        EquityHistory.portfolio_id == portfolio_id,
                        EquityHistory.date == date.date()
                    )
                ).first()
                
                if existing:
                    # Update existing record
                    existing.equity = equity
                    existing.cash = cash
                    existing.daily_return = daily_return
                    existing.n_positions = n_positions
                else:
                    # Create new record
                    equity_record = EquityHistory(
                        portfolio_id=portfolio_id,
                        date=date.date(),
                        equity=equity,
                        cash=cash,
                        daily_return=daily_return,
                        n_positions=n_positions,
                    )
                    db.add(equity_record)
                
                db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error recording equity snapshot: {str(e)}")
            return False
    
    # ==================== File-based Methods (Fallback) ====================
    
    def load_state_from_file(self) -> Optional[Dict]:
        """Load portfolio state from JSON file (fallback)"""
        try:
            if os.path.exists(self.live_state_path):
                with open(self.live_state_path, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Error loading state from file: {str(e)}")
            return None
    
    def load_equity_from_file(self) -> List[EquityPoint]:
        """Load equity history from CSV file (fallback)"""
        try:
            if not os.path.exists(self.live_equity_path):
                return []
            
            df = pd.read_csv(self.live_equity_path)
            
            points = []
            for idx, row in df.iterrows():
                points.append(EquityPoint(
                    date=str(row.get('date', '')),
                    equity=float(row.get('equity', 0)),
                    cash=float(row.get('cash', 0)),
                    portfolio_value=float(row.get('equity', 0)) + float(row.get('cash', 0)),
                    daily_return=float(row.get('daily_return', 0)),
                    n_positions=int(row.get('n_positions', 0)),
                ))
            
            return points
            
        except Exception as e:
            logger.error(f"Error loading equity from file: {str(e)}")
            return []
    
    def load_trades_from_file(self) -> List[TradeSchema]:
        """Load trades from CSV file (fallback)"""
        try:
            if not os.path.exists(self.live_trades_path):
                return []
            
            df = pd.read_csv(self.live_trades_path)
            
            trades = []
            for idx, row in df.iterrows():
                trades.append(TradeSchema(
                    entry_date=pd.Timestamp(row['entry_date']).to_pydatetime(),
                    exit_date=pd.Timestamp(row['exit_date']).to_pydatetime() if pd.notna(row.get('exit_date')) else None,
                    symbol=str(row.get('symbol', '')),
                    entry_price=float(row.get('entry_price', 0)),
                    exit_price=float(row.get('exit_price', 0)) if pd.notna(row.get('exit_price')) else None,
                    shares=int(row.get('shares', 0)),
                    realized_pnl_pct=float(row.get('realized_pnl_pct', 0)) if pd.notna(row.get('realized_pnl_pct')) else None,
                    exit_reason=str(row.get('exit_reason', 'UNKNOWN')),
                    days_held=int(row.get('days_held', 0)) if pd.notna(row.get('days_held')) else None,
                ))
            
            return trades
            
        except Exception as e:
            logger.error(f"Error loading trades from file: {str(e)}")
            return []
    
    # ==================== Public API Methods ====================
    
    def get_portfolio_state(self, portfolio_id: Optional[int] = None, use_file_fallback: bool = True) -> PortfolioState:
        """
        Get portfolio state from database or file
        
        Args:
            portfolio_id: Database portfolio ID. If None, tries file-based fallback
            use_file_fallback: Fall back to file-based data if DB not available
        """
        try:
            # Try database first if portfolio_id provided
            if portfolio_id and portfolio_id > 0:
                portfolio = self.get_portfolio_from_db(portfolio_id)
                if portfolio:
                    positions = self.get_active_positions_from_db(portfolio_id)
                    
                    pending_buys = []
                    with get_db_context() as db:
                        pending_signals = db.query(Signal).filter(
                            and_(
                                Signal.portfolio_id == portfolio_id,
                                Signal.is_executed == False,
                                Signal.signal_type == "BUY"
                            )
                        ).all()
                        
                        pending_buys = [
                            {
                                "symbol": s.symbol,
                                "confidence_score": s.confidence_score,
                                "sector": s.sector,
                            }
                            for s in pending_signals
                        ]
                    
                    return PortfolioState(
                        cash=portfolio.current_cash,
                        positions=positions,
                        pending_buys=pending_buys,
                        last_date=portfolio.last_updated.strftime("%Y-%m-%d"),
                    )
            
            # Fallback to file-based
            if use_file_fallback:
                state_data = self.load_state_from_file()
                if state_data:
                    return PortfolioState(
                        cash=state_data.get('cash', 0),
                        positions=[
                            PositionSchema(**pos) for pos in state_data.get('positions', [])
                        ],
                        pending_buys=state_data.get('pending_buys', []),
                        last_date=state_data.get('last_date', datetime.now().strftime("%Y-%m-%d")),
                    )
            
            # Return empty state if nothing found
            return PortfolioState(
                cash=0,
                positions=[],
                pending_buys=[],
                last_date=datetime.now().strftime("%Y-%m-%d"),
            )
            
        except Exception as e:
            logger.error(f"Error getting portfolio state: {str(e)}")
            return PortfolioState(
                cash=0,
                positions=[],
                pending_buys=[],
                last_date=datetime.now().strftime("%Y-%m-%d"),
            )
    
    def get_equity_history(self, portfolio_id: Optional[int] = None, use_file_fallback: bool = True) -> List[EquityPoint]:
        """Get equity history from database or file"""
        try:
            if portfolio_id and portfolio_id > 0:
                return self.get_equity_history_from_db(portfolio_id)
            
            if use_file_fallback:
                return self.load_equity_from_file()
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting equity history: {str(e)}")
            return []
    
    def get_trades_history(self, portfolio_id: Optional[int] = None, use_file_fallback: bool = True) -> List[TradeSchema]:
        """Get trades history from database or file"""
        try:
            if portfolio_id and portfolio_id > 0:
                return self.get_trades_from_db(portfolio_id)
            
            if use_file_fallback:
                return self.load_trades_from_file()
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting trades history: {str(e)}")
            return []
    
    def get_portfolio_summary(self, portfolio_id: Optional[int] = None) -> Dict:
        """Get portfolio summary statistics"""
        try:
            equity_history = self.get_equity_history(portfolio_id)
            trades_history = self.get_trades_history(portfolio_id)
            
            if not equity_history:
                return {
                    "total_return_pct": 0,
                    "daily_return_pct": 0,
                    "max_drawdown_pct": 0,
                    "sharpe_ratio": 0,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate_pct": 0,
                    "avg_win_pct": 0,
                    "avg_loss_pct": 0,
                }
            
            # Calculate metrics
            current_equity = equity_history[-1].equity if equity_history else 0
            initial_equity = equity_history[0].equity if equity_history else 0
            
            total_return = ((current_equity - initial_equity) / initial_equity * 100) if initial_equity > 0 else 0
            
            daily_returns = [eq.daily_return for eq in equity_history if eq.daily_return is not None]
            daily_return_avg = sum(daily_returns) / len(daily_returns) if daily_returns else 0
            
            # Calculate max drawdown
            max_equity = max([eq.equity for eq in equity_history]) if equity_history else 1
            min_equity = min([eq.equity for eq in equity_history]) if equity_history else 1
            max_drawdown = ((min_equity - max_equity) / max_equity * 100) if max_equity > 0 else 0
            
            # Trade statistics
            winning_trades = len([t for t in trades_history if t.realized_pnl_pct and t.realized_pnl_pct > 0])
            losing_trades = len([t for t in trades_history if t.realized_pnl_pct and t.realized_pnl_pct <= 0])
            
            win_rate = (winning_trades / len(trades_history) * 100) if trades_history else 0
            
            winning_returns = [t.realized_pnl_pct for t in trades_history if t.realized_pnl_pct and t.realized_pnl_pct > 0]
            losing_returns = [t.realized_pnl_pct for t in trades_history if t.realized_pnl_pct and t.realized_pnl_pct <= 0]
            
            avg_win = sum(winning_returns) / len(winning_returns) if winning_returns else 0
            avg_loss = sum(losing_returns) / len(losing_returns) if losing_returns else 0
            
            # Sharpe ratio (simplified: returns / std_dev * sqrt(252))
            if daily_returns and len(daily_returns) > 1:
                import statistics
                std_dev = statistics.stdev(daily_returns)
                sharpe = (daily_return_avg / std_dev * (252 ** 0.5)) if std_dev > 0 else 0
            else:
                sharpe = 0
            
            return {
                "total_return_pct": round(total_return, 2),
                "daily_return_pct": round(daily_return_avg, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "sharpe_ratio": round(sharpe, 2),
                "total_trades": len(trades_history),
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate_pct": round(win_rate, 2),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio summary: {str(e)}")
            return {}


# Initialize service
enhanced_portfolio_service = EnhancedPortfolioService()
