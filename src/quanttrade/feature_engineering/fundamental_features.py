"""
Fundamental Feature Engineering Agent (A2.2)

This module processes financial statements from data/processed/mali_tablo/
and aligns them with announcement dates from data/processed/announcements/
to create period-level fundamental features.

Input:
    - data/processed/mali_tablo/*_financials_long.csv
        Columns: symbol, period, item_code, item_name_tr, item_name_en, value
    - data/processed/announcements/*_announcements_clean.csv
        Columns: symbol, index, announcement_date, ruleType, summary, url

Output:
    - data/features/fundamental/{SYMBOL}_fundamental_period_features.csv
        Columns: symbol, period, announcement_date, ratios, raw financial items
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FundamentalFeatureEngineer:
    """
    Processes financial statements and creates fundamental features with announcement dates.
    """
    
    # Turkish financial item name to feature name mapping
    ITEM_MAPPING = {
        'net_profit': ['NET DÖNEM KARI', 'NET KAR', 'DÖNEM NET KARI', 'DÖNEM KARI'],
        'net_sales': ['NET SATIŞLAR', 'HASILAT', 'NET SATIŞ'],
        'total_assets': ['TOPLAM VARLIKLAR', 'AKTİF TOPLAMI'],
        'total_liabilities': ['TOPLAM YÜKÜMLÜLÜKLER', 'TOPLAM BORÇLAR', 'PASİF TOPLAMI'],
        'total_equity': ['ÖZKAYNAKLAR', 'SERMAYE'],
        'current_liabilities': ['KISA VADELİ YÜKÜMLÜLÜKLER', 'KISA VADELİ BORÇLAR'],
        'current_assets': ['DÖNEN VARLIKLAR'],
        'long_term_liabilities': ['UZUN VADELİ YÜKÜMLÜLÜKLER', 'UZUN VADELİ BORÇLAR'],
        'revenue': ['HASILAT', 'NET SATIŞLAR', 'BRÜT SATIŞLAR'],
        'operating_profit': ['FAALİYET KARI', 'ESAS FAALİYET KARI'],
        'ebitda': ['FAVÖK', 'EBITDA'],
        'gross_profit': ['BRÜT KAR', 'BRÜT SATIŞ KARI'],
    }
    
    def __init__(self, base_path: str = None):
        """
        Initialize the fundamental feature engineer.
        
        Args:
            base_path: Base path to the QuantTrade project
        """
        if base_path is None:
            # Auto-detect base path (assumes script is in src/quanttrade/feature_engineering/)
            self.base_path = Path(__file__).parent.parent.parent.parent
        else:
            self.base_path = Path(base_path)
            
        self.mali_tablo_path = self.base_path / 'data' / 'processed' / 'mali_tablo'
        self.announcements_path = self.base_path / 'data' / 'processed' / 'announcements'
        self.output_path = self.base_path / 'data' / 'features' / 'fundamental'
        
        # Create output directory if it doesn't exist
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Base path: {self.base_path}")
        logger.info(f"Mali tablo path: {self.mali_tablo_path}")
        logger.info(f"Announcements path: {self.announcements_path}")
        logger.info(f"Output path: {self.output_path}")
    
    def _find_item_value(self, df: pd.DataFrame, period: str, feature_names: list) -> Optional[float]:
        """
        Find the value of a financial item by searching for Turkish keywords.
        
        Args:
            df: DataFrame with financial data for a symbol
            period: Period to search for (e.g., '2022/12')
            feature_names: List of possible Turkish names for the item
            
        Returns:
            Value of the item or None if not found
        """
        period_data = df[df['period'] == period]
        
        for name in feature_names:
            # Case-insensitive search in item_name_tr
            matches = period_data[
                period_data['item_name_tr'].str.contains(name, case=False, na=False)
            ]
            
            if not matches.empty:
                # Return the first match value
                return matches.iloc[0]['value']
        
        return None
    
    def _pivot_financials(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert long format financial data to wide format with mapped feature names.
        
        Args:
            df: Long format financial DataFrame
            
        Returns:
            Wide format DataFrame with symbol, period, and financial items as columns
        """
        periods = df['period'].unique()
        symbol = df['symbol'].iloc[0]
        
        rows = []
        for period in periods:
            row = {
                'symbol': symbol,
                'period': period
            }
            
            # Extract each mapped financial item
            for feature_name, turkish_names in self.ITEM_MAPPING.items():
                value = self._find_item_value(df, period, turkish_names)
                row[feature_name] = value
            
            rows.append(row)
        
        wide_df = pd.DataFrame(rows)
        
        # Calculate total_debt if not directly available
        if 'total_debt' not in wide_df.columns or wide_df['total_debt'].isna().all():
            wide_df['total_debt'] = (
                wide_df['current_liabilities'].fillna(0) + 
                wide_df['long_term_liabilities'].fillna(0)
            )
        
        return wide_df
    
    def _calculate_ratios(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate financial ratios from raw financial items.
        
        Args:
            df: Wide format DataFrame with financial items
            
        Returns:
            DataFrame with added ratio columns
        """
        result = df.copy()
        
        # Profitability ratios
        result['roe'] = np.where(
            (result['total_equity'].notna()) & (result['total_equity'] != 0),
            result['net_profit'] / result['total_equity'],
            np.nan
        )
        
        result['roa'] = np.where(
            (result['total_assets'].notna()) & (result['total_assets'] != 0),
            result['net_profit'] / result['total_assets'],
            np.nan
        )
        
        result['net_margin'] = np.where(
            (result['net_sales'].notna()) & (result['net_sales'] != 0),
            result['net_profit'] / result['net_sales'],
            np.nan
        )
        
        # Leverage & liquidity ratios
        result['debt_to_equity'] = np.where(
            (result['total_equity'].notna()) & (result['total_equity'] != 0),
            result['total_debt'] / result['total_equity'],
            np.nan
        )
        
        result['current_ratio'] = np.where(
            (result['current_liabilities'].notna()) & (result['current_liabilities'] != 0),
            result['current_assets'] / result['current_liabilities'],
            np.nan
        )
        
        return result
    
    def _calculate_yoy_growth(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate year-over-year growth metrics.
        
        Args:
            df: DataFrame with financial data sorted by period
            
        Returns:
            DataFrame with YoY growth columns added
        """
        result = df.copy()
        
        # Convert period to datetime for easier manipulation
        result['period_dt'] = pd.to_datetime(result['period'], format='%Y/%m')
        result = result.sort_values('period_dt')
        
        # Extract quarter (1, 2, 3, or 4)
        result['quarter'] = result['period_dt'].dt.quarter
        result['year'] = result['period_dt'].dt.year
        
        # Revenue YoY growth
        result['revenue_growth_yoy'] = np.nan
        result['profit_growth_yoy'] = np.nan
        
        for idx in result.index:
            current_quarter = result.loc[idx, 'quarter']
            current_year = result.loc[idx, 'year']
            
            # Find same quarter from previous year
            prev_year_data = result[
                (result['quarter'] == current_quarter) & 
                (result['year'] == current_year - 1)
            ]
            
            if not prev_year_data.empty:
                prev_sales = prev_year_data.iloc[0]['net_sales']
                current_sales = result.loc[idx, 'net_sales']
                
                if pd.notna(prev_sales) and pd.notna(current_sales) and prev_sales != 0:
                    result.loc[idx, 'revenue_growth_yoy'] = (current_sales - prev_sales) / prev_sales
                
                prev_profit = prev_year_data.iloc[0]['net_profit']
                current_profit = result.loc[idx, 'net_profit']
                
                if pd.notna(prev_profit) and pd.notna(current_profit) and prev_profit != 0:
                    result.loc[idx, 'profit_growth_yoy'] = (current_profit - prev_profit) / prev_profit
        
        # Drop temporary columns
        result = result.drop(['period_dt', 'quarter', 'year'], axis=1)
        
        return result
    
    def _match_announcement_dates(
        self, 
        financial_df: pd.DataFrame, 
        announcements_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Match each financial period with its announcement date.
        
        Args:
            financial_df: DataFrame with financial periods
            announcements_df: DataFrame with announcement dates
            
        Returns:
            DataFrame with announcement_date column added
        """
        result = financial_df.copy()
        result['announcement_date'] = pd.NaT
        
        # Convert period to datetime for matching
        result['period_end'] = pd.to_datetime(result['period'], format='%Y/%m') + pd.offsets.MonthEnd(0)
        
        # Ensure announcement_date is datetime
        announcements_df['announcement_date'] = pd.to_datetime(announcements_df['announcement_date'])
        
        # For each period, find the closest announcement date after the period end
        for idx in result.index:
            period_end = result.loc[idx, 'period_end']
            
            # Filter announcements after or close to the period end
            # Allow some flexibility (announcements within 120 days after period end)
            candidate_announcements = announcements_df[
                (announcements_df['announcement_date'] >= period_end) &
                (announcements_df['announcement_date'] <= period_end + pd.Timedelta(days=120))
            ].sort_values('announcement_date')
            
            if not candidate_announcements.empty:
                # Take the first (earliest) announcement
                result.loc[idx, 'announcement_date'] = candidate_announcements.iloc[0]['announcement_date']
            else:
                # If no announcement found in the next 120 days, look for the closest one
                all_after = announcements_df[
                    announcements_df['announcement_date'] >= period_end
                ].sort_values('announcement_date')
                
                if not all_after.empty:
                    result.loc[idx, 'announcement_date'] = all_after.iloc[0]['announcement_date']
        
        result = result.drop('period_end', axis=1)
        
        return result
    
    def process_symbol(self, symbol: str) -> bool:
        """
        Process a single symbol and generate fundamental features.
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing {symbol}...")
            
            # Load financial data
            financial_file = self.mali_tablo_path / f"{symbol}_financials_long.csv"
            if not financial_file.exists():
                logger.warning(f"Financial file not found for {symbol}")
                return False
            
            financial_df = pd.read_csv(financial_file)
            
            # Load announcement data
            announcement_file = self.announcements_path / f"{symbol}_announcements_clean.csv"
            if not announcement_file.exists():
                logger.warning(f"Announcement file not found for {symbol}")
                return False
            
            announcements_df = pd.read_csv(announcement_file)
            
            # Step 1: Pivot financials to wide format
            logger.info(f"  Pivoting financial data...")
            wide_df = self._pivot_financials(financial_df)
            
            if wide_df.empty:
                logger.warning(f"No data after pivoting for {symbol}")
                return False
            
            # Step 2: Calculate ratios
            logger.info(f"  Calculating financial ratios...")
            ratio_df = self._calculate_ratios(wide_df)
            
            # Step 3: Calculate YoY growth
            logger.info(f"  Calculating YoY growth metrics...")
            growth_df = self._calculate_yoy_growth(ratio_df)
            
            # Step 4: Match with announcement dates
            logger.info(f"  Matching announcement dates...")
            final_df = self._match_announcement_dates(growth_df, announcements_df)
            
            # Reorder columns for output
            ratio_cols = ['roe', 'roa', 'net_margin', 'debt_to_equity', 'current_ratio', 
                         'revenue_growth_yoy', 'profit_growth_yoy']
            
            raw_item_cols = [col for col in final_df.columns 
                           if col not in ['symbol', 'period', 'announcement_date'] + ratio_cols]
            
            output_cols = ['symbol', 'period', 'announcement_date'] + ratio_cols + raw_item_cols
            
            # Filter to only existing columns
            output_cols = [col for col in output_cols if col in final_df.columns]
            
            final_df = final_df[output_cols]
            
            # Save output
            output_file = self.output_path / f"{symbol}_fundamental_period_features.csv"
            final_df.to_csv(output_file, index=False)
            
            logger.info(f"  ✓ Saved {len(final_df)} periods to {output_file.name}")
            logger.info(f"  Date range: {final_df['period'].min()} to {final_df['period'].max()}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}", exc_info=True)
            return False
    
    def process_all_symbols(self) -> Tuple[int, int]:
        """
        Process all symbols found in the mali_tablo directory.
        
        Returns:
            Tuple of (successful_count, failed_count)
        """
        # Get all financial files
        financial_files = list(self.mali_tablo_path.glob("*_financials_long.csv"))
        symbols = [f.stem.replace('_financials_long', '') for f in financial_files]
        
        logger.info(f"Found {len(symbols)} symbols to process")
        
        successful = 0
        failed = 0
        
        for symbol in sorted(symbols):
            if self.process_symbol(symbol):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing complete!")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Output directory: {self.output_path}")
        logger.info(f"{'='*60}")
        
        return successful, failed


def main():
    """Main execution function."""
    engineer = FundamentalFeatureEngineer()
    engineer.process_all_symbols()


if __name__ == "__main__":
    main()
