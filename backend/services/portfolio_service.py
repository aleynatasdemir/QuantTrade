"""
Portfolio Service - Load and manage portfolio data
"""
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from config import settings
from models.schemas import PortfolioState, EquityPoint, Trade


class PortfolioService:
    """Service for managing portfolio data"""
    
    def __init__(self):
        self.state_path = settings.get_absolute_path(settings.live_state_path)
        self.equity_path = settings.get_absolute_path(settings.live_equity_path)
        self.trades_path = settings.get_absolute_path(settings.live_trades_path)
    
    def get_portfolio_state(self) -> PortfolioState:
        """Load current portfolio state from JSON file"""
        try:
            if not self.state_path.exists():
                # Return default state if file doesn't exist
                return PortfolioState(
                    cash=100000.0,
                    positions=[],
                    pending_buys=[],
                    last_date=None
                )
            
            with open(self.state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ensure avg_price and current_price exist for frontend compatibility
            if 'positions' in data:
                for pos in data['positions']:
                    # Keep existing current_price if available, otherwise use entry_price
                    if 'current_price' not in pos and 'entry_price' in pos:
                        pos['current_price'] = pos['entry_price']
                    if 'avg_price' not in pos and 'entry_price' in pos:
                        pos['avg_price'] = pos['entry_price']
            
            return PortfolioState(**data)
        except Exception as e:
            raise RuntimeError(f"Failed to load portfolio state: {str(e)}")
    
    def get_equity_history(self) -> List[EquityPoint]:
        """Load equity history from CSV file"""
        try:
            if not self.equity_path.exists():
                return []
            
            df = pd.read_csv(self.equity_path)
            
            # Convert DataFrame to list of EquityPoint models
            equity_points = []
            for _, row in df.iterrows():
                equity_points.append(EquityPoint(
                    date=str(row['date']),
                    equity=float(row['equity']),
                    cash=float(row['cash']),
                    portfolio_value=float(row['portfolio_value']),
                    daily_return=float(row['daily_return']),
                    n_positions=int(row['n_positions'])
                ))
            
            return equity_points
        except Exception as e:
            raise RuntimeError(f"Failed to load equity history: {str(e)}")
    
    def get_trades_history(self) -> List[Trade]:
        """Load trade history from CSV file"""
        try:
            if not self.trades_path.exists():
                return []
            
            df = pd.read_csv(self.trades_path)
            
            # Convert DataFrame to list of Trade models
            trades = []
            for _, row in df.iterrows():
                trades.append(Trade(
                    entry_date=str(row['entry_date']),
                    exit_date=str(row['exit_date']) if pd.notna(row['exit_date']) else "",
                    symbol=str(row['symbol']),
                    entry_price=float(row['entry_price']),
                    exit_price=float(row['exit_price']) if pd.notna(row['exit_price']) else None,
                    shares=int(row['shares']),
                    return_pct=float(row['return']) if pd.notna(row['return']) else None,
                    reason=str(row['reason']),
                    days_held=int(row['days_held'])
                ))
            
            return trades
        except Exception as e:
            raise RuntimeError(f"Failed to load trades history: {str(e)}")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get a summary of portfolio metrics"""
        state = self.get_portfolio_state()
        equity_history = self.get_equity_history()
        
        # Calculate total equity
        total_equity = state.cash
        for pos in state.positions:
            total_equity += pos.shares * pos.entry_price
        
        # Calculate returns
        total_return = 0.0
        if equity_history:
            initial_equity = equity_history[0].equity
            current_equity = equity_history[-1].equity
            total_return = ((current_equity - initial_equity) / initial_equity) * 100
        
        return {
            "total_equity": total_equity,
            "cash": state.cash,
            "n_positions": len(state.positions),
            "n_pending": len(state.pending_buys),
            "total_return_pct": total_return,
            "last_update": state.last_date
        }


# Global service instance
portfolio_service = PortfolioService()
