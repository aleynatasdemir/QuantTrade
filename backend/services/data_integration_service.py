"""
Data Integration Service
Handles synchronization between master_df.parquet and PostgreSQL database
"""
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.database import get_db_context
from models.orm_models import Signal, PriceData, MacroData
from models.schemas import SignalCreate

logger = logging.getLogger(__name__)


class DataIntegrationService:
    """Service for integrating data from files into PostgreSQL"""
    
    def __init__(self):
        self.master_df_path = os.getenv("MASTER_DF_PATH", 
                                       "data/master/master_df.parquet")
        self.price_data_path = os.getenv("DATA_PATH", "data")
        self.macro_data_path = os.getenv("DATA_PATH", "data")
        
    def load_master_df(self) -> Optional[pd.DataFrame]:
        """Load master feature dataframe from parquet file"""
        try:
            if not os.path.exists(self.master_df_path):
                logger.error(f"Master dataframe not found at {self.master_df_path}")
                return None
            
            df = pd.read_parquet(self.master_df_path)
            logger.info(f"Loaded master_df with shape {df.shape}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading master_df: {str(e)}")
            return None
    
    def extract_signals_from_master_df(self, master_df: pd.DataFrame, 
                                      user_id: int, portfolio_id: Optional[int] = None) -> List[Dict]:
        """
        Extract BUY signals from master_df based on model scores
        
        Expects master_df to have columns: symbol, model_score, sector, date
        """
        try:
            signals = []
            
            if master_df is None or master_df.empty:
                return signals
            
            # Ensure required columns exist
            required_cols = ['symbol', 'model_score', 'sector', 'date']
            if not all(col in master_df.columns for col in required_cols):
                logger.warning(f"master_df missing required columns. Has: {master_df.columns.tolist()}")
                return signals
            
            # Filter for high confidence scores (top 20%)
            master_df_sorted = master_df.nlargest(max(1, int(len(master_df) * 0.2)), 'model_score')
            
            for idx, row in master_df_sorted.iterrows():
                signal = {
                    "user_id": user_id,
                    "portfolio_id": portfolio_id,
                    "symbol": str(row['symbol']).upper(),
                    "signal_type": "BUY",
                    "signal_date": pd.Timestamp(row['date']).to_pydatetime(),
                    "confidence_score": float(row['model_score']),
                    "model_name": "CatBoost_T1",
                    "sector": str(row.get('sector', 'Unknown')),
                }
                signals.append(signal)
                
            logger.info(f"Extracted {len(signals)} BUY signals from master_df")
            return signals
            
        except Exception as e:
            logger.error(f"Error extracting signals from master_df: {str(e)}")
            return []
    
    def sync_signals_to_db(self, user_id: int, portfolio_id: Optional[int] = None) -> Dict:
        """
        Load master_df and sync new signals to database
        """
        try:
            # Load master dataframe
            master_df = self.load_master_df()
            if master_df is None:
                return {"status": "error", "message": "Failed to load master_df"}
            
            # Extract signals
            signals_data = self.extract_signals_from_master_df(master_df, user_id, portfolio_id)
            
            if not signals_data:
                return {"status": "success", "signals_synced": 0, "message": "No signals extracted"}
            
            # Save to database
            with get_db_context() as db:
                signals_created = 0
                
                for signal_data in signals_data:
                    # Check if signal already exists for this symbol and date
                    existing_signal = db.query(Signal).filter(
                        Signal.symbol == signal_data['symbol'],
                        Signal.signal_date == signal_data['signal_date'],
                        Signal.user_id == user_id
                    ).first()
                    
                    if not existing_signal:
                        signal = Signal(**signal_data)
                        db.add(signal)
                        signals_created += 1
                
                db.commit()
                logger.info(f"Synced {signals_created} new signals to database")
                
            return {
                "status": "success",
                "signals_synced": signals_created,
                "total_signals_in_batch": len(signals_data),
                "message": f"Successfully synced {signals_created} signals"
            }
            
        except Exception as e:
            logger.error(f"Error syncing signals to database: {str(e)}")
            return {"status": "error", "message": f"Sync failed: {str(e)}"}
    
    def load_price_data_from_csv(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load price data for specific symbol from CSV"""
        try:
            csv_path = os.path.join(self.price_data_path, "processed", "ohlcv", f"{symbol}.csv")
            
            if not os.path.exists(csv_path):
                logger.warning(f"Price data not found for {symbol} at {csv_path}")
                return None
            
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded price data for {symbol}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error loading price data for {symbol}: {str(e)}")
            return None
    
    def sync_price_data_to_db(self, symbols: Optional[List[str]] = None) -> Dict:
        """
        Sync OHLCV price data to database for specified symbols
        """
        try:
            if symbols is None:
                symbols = []
            
            with get_db_context() as db:
                total_synced = 0
                
                for symbol in symbols:
                    price_df = self.load_price_data_from_csv(symbol)
                    
                    if price_df is None or price_df.empty:
                        continue
                    
                    # Ensure required columns
                    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                    if not all(col in price_df.columns for col in required_cols):
                        logger.warning(f"Price data for {symbol} missing required columns")
                        continue
                    
                    synced_count = 0
                    for idx, row in price_df.iterrows():
                        # Check if record already exists
                        existing = db.query(PriceData).filter(
                            PriceData.symbol == symbol,
                            PriceData.date == pd.Timestamp(row['date']).to_pydatetime()
                        ).first()
                        
                        if not existing:
                            price_record = PriceData(
                                symbol=symbol,
                                date=pd.Timestamp(row['date']).to_pydatetime(),
                                open_price=float(row.get('open', 0)),
                                high_price=float(row.get('high', 0)),
                                low_price=float(row.get('low', 0)),
                                close_price=float(row.get('close', 0)),
                                volume=int(row.get('volume', 0)),
                                sma_20=float(row.get('sma_20', None)) if pd.notna(row.get('sma_20')) else None,
                                sma_50=float(row.get('sma_50', None)) if pd.notna(row.get('sma_50')) else None,
                                sma_200=float(row.get('sma_200', None)) if pd.notna(row.get('sma_200')) else None,
                                rsi_14=float(row.get('rsi_14', None)) if pd.notna(row.get('rsi_14')) else None,
                            )
                            db.add(price_record)
                            synced_count += 1
                    
                    db.commit()
                    total_synced += synced_count
                    logger.info(f"Synced {synced_count} price records for {symbol}")
                
                return {
                    "status": "success",
                    "total_records_synced": total_synced,
                    "symbols_processed": len(symbols),
                    "message": f"Successfully synced {total_synced} price records"
                }
                
        except Exception as e:
            logger.error(f"Error syncing price data: {str(e)}")
            return {"status": "error", "message": f"Sync failed: {str(e)}"}
    
    def get_latest_signals(self, limit: int = 10) -> List[Dict]:
        """Get latest signals from database"""
        try:
            with get_db_context() as db:
                signals = db.query(Signal).order_by(Signal.signal_date.desc()).limit(limit).all()
                
                return [
                    {
                        "id": s.id,
                        "symbol": s.symbol,
                        "signal_type": s.signal_type,
                        "signal_date": s.signal_date,
                        "confidence_score": s.confidence_score,
                        "is_executed": s.is_executed,
                        "sector": s.sector,
                    }
                    for s in signals
                ]
                
        except Exception as e:
            logger.error(f"Error retrieving latest signals: {str(e)}")
            return []
    
    def get_signal_stats(self) -> Dict:
        """Get statistics on signals in database"""
        try:
            with get_db_context() as db:
                total_signals = db.query(func.count(Signal.id)).scalar() or 0
                executed_signals = db.query(func.count(Signal.id)).filter(Signal.is_executed == True).scalar() or 0
                avg_confidence = db.query(func.avg(Signal.confidence_score)).scalar() or 0
                
                return {
                    "total_signals": total_signals,
                    "executed_signals": executed_signals,
                    "pending_signals": total_signals - executed_signals,
                    "average_confidence_score": float(avg_confidence),
                    "execution_rate_pct": (executed_signals / total_signals * 100) if total_signals > 0 else 0,
                }
                
        except Exception as e:
            logger.error(f"Error retrieving signal stats: {str(e)}")
            return {}


# Initialize service
data_integration_service = DataIntegrationService()
