import pandas as pd
import numpy as np
from typing import Dict, List, Any

class BacktestEngine:
    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.001):
        """
        Initialize the BacktestEngine.
        
        Args:
            initial_capital: Starting capital for the portfolio.
            commission: Transaction cost per trade (e.g., 0.001 for 0.1%).
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.portfolio_value = []
        self.positions = []
        self.trades = []

    def run_backtest(self, df: pd.DataFrame, predictions: np.ndarray, price_col: str = 'price_close') -> pd.DataFrame:
        """
        Run a simple backtest strategy:
        - Prediction made at day t using data up to day t
        - Trade executed at day t+1 open price (realistic)
        - Buy if prediction is 1 (Up) and we don't have a position.
        - Sell if prediction is 0 (Down) and we have a position.
        
        Args:
            df: DataFrame containing price data.
            predictions: Array of model predictions (0 or 1).
            price_col: Name of the column containing the closing price (for portfolio valuation).
            
        Returns:
            DataFrame with portfolio value over time.
        """
        cash = self.initial_capital
        position = 0 # 0: No position, 1: Long position
        shares = 0
        
        results = df.copy()
        results['prediction'] = predictions
        results['portfolio_value'] = self.initial_capital
        
        # Initialize columns for tracking
        results['position'] = 0
        results['cash'] = self.initial_capital
        results['shares'] = 0
        
        for i in range(len(results) - 1):  # Stop at len-1 to avoid looking ahead
            current_price = results[price_col].iloc[i]
            pred = results['prediction'].iloc[i]
            date = results.index[i] if isinstance(results.index, pd.DatetimeIndex) else i
            
            # CRITICAL FIX: Use NEXT day's open price for trading
            next_open_price = results['price_open'].iloc[i + 1]
            
            # Simple Strategy Logic
            if pred == 1 and position == 0:
                # Buy Signal - execute at next day's open
                shares = (cash * (1 - self.commission)) / next_open_price
                cash = 0
                position = 1
                self.trades.append({'date': date, 'type': 'BUY', 'price': next_open_price, 'shares': shares})
                
            elif pred == 0 and position == 1:
                # Sell Signal - execute at next day's open
                cash = shares * next_open_price * (1 - self.commission)
                shares = 0
                position = 0
                self.trades.append({'date': date, 'type': 'SELL', 'price': next_open_price, 'shares': shares})
            
            # Update portfolio value using current day's close
            current_value = cash + (shares * current_price)
            results.iloc[i, results.columns.get_loc('portfolio_value')] = current_value
            self.portfolio_value.append(current_value)
        
        # Handle last day
        last_price = results[price_col].iloc[-1]
        final_value = cash + (shares * last_price)
        results.iloc[-1, results.columns.get_loc('portfolio_value')] = final_value
        self.portfolio_value.append(final_value)
            
        return results

    def calculate_metrics(self, results: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate performance metrics.
        """
        final_value = results['portfolio_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Daily returns
        results['daily_return'] = results['portfolio_value'].pct_change()
        
        # Sharpe Ratio (assuming 252 trading days, risk-free rate 0 for simplicity)
        mean_return = results['daily_return'].mean()
        std_return = results['daily_return'].std()
        sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return != 0 else 0
        
        # Max Drawdown
        cumulative_max = results['portfolio_value'].cummax()
        drawdown = (results['portfolio_value'] - cumulative_max) / cumulative_max
        max_drawdown = drawdown.min()
        
        return {
            'Initial Capital': self.initial_capital,
            'Final Value': final_value,
            'Total Return': total_return,
            'Sharpe Ratio': sharpe_ratio,
            'Max Drawdown': max_drawdown,
            'Total Trades': len(self.trades)
        }
