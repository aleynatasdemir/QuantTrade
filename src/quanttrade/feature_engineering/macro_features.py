"""
Macro Feature Engineering Agent (A2.3)

This module processes macro-economic data from data/processed/macro/
and creates derivative features (ROC, YoY, MoM, etc.).

Input:
    - data/processed/macro/evds_macro_daily_clean.csv
        Columns: date, usd_try, eur_try, bist100, m2, cpi, tcmb_repo, us_cli, us_cpi

Output:
    - data/features/macro/macro_features_daily.csv
        Date-indexed table with all macro features and their derivatives
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, Optional
import warnings

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MacroFeatureEngineer:
    """
    Processes macro-economic data and creates derivative features.
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize the macro feature engineer.
        
        Args:
            base_path: Base path to the QuantTrade project
        """
        if base_path is None:
            # Auto-detect base path (assumes script is in src/quanttrade/feature_engineering/)
            self.base_path = Path(__file__).parent.parent.parent.parent
        else:
            self.base_path = Path(base_path)
            
        self.macro_path = self.base_path / 'data' / 'processed' / 'macro'
        self.output_path = self.base_path / 'data' / 'features' / 'macro'
        
        # Create output directory if it doesn't exist
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Base path: {self.base_path}")
        logger.info(f"Macro data path: {self.macro_path}")
        logger.info(f"Output path: {self.output_path}")
    
    def _calculate_roc(self, series: pd.Series, periods: int) -> pd.Series:
        """
        Calculate rate of change (percentage change).
        
        Args:
            series: Time series data
            periods: Number of periods to look back
            
        Returns:
            Rate of change series
        """
        return series.pct_change(periods)
    
    def _calculate_diff(self, series: pd.Series, periods: int = 1) -> pd.Series:
        """
        Calculate absolute difference.
        
        Args:
            series: Time series data
            periods: Number of periods to look back
            
        Returns:
            Difference series
        """
        return series.diff(periods)
    
    def _calculate_yoy(self, series: pd.Series, freq: str = 'monthly') -> pd.Series:
        """
        Calculate year-over-year change.
        
        Args:
            series: Time series data
            freq: Frequency of the data ('monthly' or 'daily')
            
        Returns:
            Year-over-year change series
        """
        if freq == 'monthly':
            # For monthly data, compare with 12 months ago
            periods = 12
        else:
            # For daily data, approximate 1 year as 252 trading days
            periods = 252
        
        return series.pct_change(periods)
    
    def _calculate_mom(self, series: pd.Series) -> pd.Series:
        """
        Calculate month-over-month change.
        
        Args:
            series: Time series data
            
        Returns:
            Month-over-month change series
        """
        # For monthly data, this is just 1-period change
        return series.pct_change(1)
    
    def generate_features(self, fill_method: str = 'ffill') -> pd.DataFrame:
        """
        Generate all macro features from the input data.
        
        Args:
            fill_method: Method to handle missing values ('ffill', 'bfill', or None)
            
        Returns:
            DataFrame with all macro features
        """
        logger.info("Loading macro data...")
        
        # Load the cleaned macro data
        input_file = self.macro_path / 'evds_macro_daily_clean.csv'
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        df = pd.read_csv(input_file)
        
        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        logger.info(f"Loaded {len(df)} days of macro data")
        logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
        logger.info(f"Columns: {list(df.columns)}")
        
        # Create result dataframe starting with the original data
        result = df.copy()
        
        # ===================================================================
        # 1. USD/TRY Features
        # ===================================================================
        logger.info("Calculating USD/TRY features...")
        
        result['usdtry_roc_1d'] = self._calculate_roc(df['usd_try'], 1)
        result['usdtry_roc_5d'] = self._calculate_roc(df['usd_try'], 5)
        result['usdtry_roc_20d'] = self._calculate_roc(df['usd_try'], 20)
        
        # ===================================================================
        # 2. EUR/TRY Features
        # ===================================================================
        logger.info("Calculating EUR/TRY features...")
        
        result['eurtry_roc_1d'] = self._calculate_roc(df['eur_try'], 1)
        result['eurtry_roc_5d'] = self._calculate_roc(df['eur_try'], 5)
        result['eurtry_roc_20d'] = self._calculate_roc(df['eur_try'], 20)
        
        # ===================================================================
        # 3. BIST100 Features
        # ===================================================================
        logger.info("Calculating BIST100 features...")
        
        result['bist100_roc_1d'] = self._calculate_roc(df['bist100'], 1)
        result['bist100_roc_5d'] = self._calculate_roc(df['bist100'], 5)
        result['bist100_roc_20d'] = self._calculate_roc(df['bist100'], 20)
        result['bist100_roc_60d'] = self._calculate_roc(df['bist100'], 60)
        
        # ===================================================================
        # 4. TCMB Repo Rate Features
        # ===================================================================
        logger.info("Calculating TCMB rate features...")
        
        # Absolute change in basis points (more intuitive for interest rates)
        result['tcmb_rate_change'] = self._calculate_diff(df['tcmb_repo'], 1)
        result['tcmb_rate_change_5d'] = self._calculate_diff(df['tcmb_repo'], 5)
        
        # Also include percentage change for consistency
        result['tcmb_rate_roc_1d'] = self._calculate_roc(df['tcmb_repo'], 1)
        
        # ===================================================================
        # 5. CPI (Inflation) Features
        # ===================================================================
        logger.info("Calculating CPI features...")
        
        # Month-over-month (for monthly CPI data)
        result['cpi_mom'] = self._calculate_mom(df['cpi'])
        
        # Year-over-year inflation rate
        # CPI is monthly, so 12 periods = 1 year
        result['cpi_yoy'] = self._calculate_yoy(df['cpi'], freq='monthly')
        
        # ===================================================================
        # 6. M2 Money Supply Features
        # ===================================================================
        logger.info("Calculating M2 features...")
        
        # Month-over-month growth
        result['m2_mom'] = self._calculate_mom(df['m2'])
        
        # Year-over-year growth
        result['m2_yoy'] = self._calculate_yoy(df['m2'], freq='monthly')
        
        # ===================================================================
        # 7. US CLI (Leading Indicators) Features
        # ===================================================================
        if 'us_cli' in df.columns:
            logger.info("Calculating US CLI features...")
            
            result['us_cli_roc_1d'] = self._calculate_roc(df['us_cli'], 1)
            result['us_cli_roc_20d'] = self._calculate_roc(df['us_cli'], 20)
        
        # ===================================================================
        # 8. US CPI Features
        # ===================================================================
        if 'us_cpi' in df.columns:
            logger.info("Calculating US CPI features...")
            
            result['us_cpi_mom'] = self._calculate_mom(df['us_cpi'])
            result['us_cpi_yoy'] = self._calculate_yoy(df['us_cpi'], freq='monthly')
        
        # ===================================================================
        # 9. Cross-Currency Features
        # ===================================================================
        logger.info("Calculating cross-currency features...")
        
        # EUR/USD implied rate
        result['eur_usd_implied'] = df['eur_try'] / df['usd_try']
        result['eur_usd_roc_1d'] = self._calculate_roc(result['eur_usd_implied'], 1)
        
        # ===================================================================
        # 10. Relative Strength Features (vs BIST100)
        # ===================================================================
        logger.info("Calculating relative strength features...")
        
        # Currency strength relative to market
        # Positive means currency weakening faster than market decline
        result['usdtry_vs_bist100'] = result['usdtry_roc_1d'] - result['bist100_roc_1d']
        result['eurtry_vs_bist100'] = result['eurtry_roc_1d'] - result['bist100_roc_1d']
        
        # ===================================================================
        # Handle Missing Values
        # ===================================================================
        if fill_method:
            logger.info(f"Filling missing values using method: {fill_method}")
            
            # Forward fill for ALL columns (base economic indicators AND derivatives)
            # This ensures monthly/weekly data is carried forward to daily frequency
            for col in result.columns:
                if col != 'date':
                    result[col] = result[col].fillna(method=fill_method)
            
            logger.info(f"✓ Forward fill applied to all {len(result.columns)-1} data columns")
        
        # ===================================================================
        # Reorder columns for better readability
        # ===================================================================
        logger.info("Reordering columns...")
        
        # Start with date
        ordered_cols = ['date']
        
        # USD/TRY block
        ordered_cols.extend(['usd_try', 'usdtry_roc_1d', 'usdtry_roc_5d', 'usdtry_roc_20d'])
        
        # EUR/TRY block
        ordered_cols.extend(['eur_try', 'eurtry_roc_1d', 'eurtry_roc_5d', 'eurtry_roc_20d'])
        
        # EUR/USD block
        ordered_cols.extend(['eur_usd_implied', 'eur_usd_roc_1d'])
        
        # BIST100 block
        ordered_cols.extend(['bist100', 'bist100_roc_1d', 'bist100_roc_5d', 
                           'bist100_roc_20d', 'bist100_roc_60d'])
        
        # TCMB rate block
        ordered_cols.extend(['tcmb_repo', 'tcmb_rate_change', 'tcmb_rate_change_5d', 
                           'tcmb_rate_roc_1d'])
        
        # Inflation block
        ordered_cols.extend(['cpi', 'cpi_mom', 'cpi_yoy'])
        
        # Money supply block
        ordered_cols.extend(['m2', 'm2_mom', 'm2_yoy'])
        
        # US indicators
        if 'us_cli' in result.columns:
            ordered_cols.extend(['us_cli', 'us_cli_roc_1d', 'us_cli_roc_20d'])
        
        if 'us_cpi' in result.columns:
            ordered_cols.extend(['us_cpi', 'us_cpi_mom', 'us_cpi_yoy'])
        
        # Relative strength
        ordered_cols.extend(['usdtry_vs_bist100', 'eurtry_vs_bist100'])
        
        # Filter to only existing columns
        ordered_cols = [col for col in ordered_cols if col in result.columns]
        
        # Add any remaining columns not explicitly ordered
        remaining_cols = [col for col in result.columns if col not in ordered_cols]
        ordered_cols.extend(remaining_cols)
        
        result = result[ordered_cols]
        
        return result
    
    def save_features(self, df: pd.DataFrame) -> str:
        """
        Save the generated features to CSV.
        
        Args:
            df: DataFrame with macro features
            
        Returns:
            Path to the saved file
        """
        output_file = self.output_path / 'macro_features_daily.csv'
        
        df.to_csv(output_file, index=False)
        
        logger.info(f"✓ Saved {len(df)} days to {output_file.name}")
        
        return str(output_file)
    
    def run(self, fill_method: str = 'ffill') -> str:
        """
        Execute the complete macro feature engineering pipeline.
        
        Args:
            fill_method: Method to handle missing values
            
        Returns:
            Path to the output file
        """
        logger.info("="*60)
        logger.info("Starting Macro Feature Engineering (A2.3)")
        logger.info("="*60)
        
        # Generate features
        features_df = self.generate_features(fill_method=fill_method)
        
        # Display summary statistics
        logger.info("\n" + "="*60)
        logger.info("Feature Summary:")
        logger.info(f"Total rows: {len(features_df)}")
        logger.info(f"Total columns: {len(features_df.columns)}")
        logger.info(f"Date range: {features_df['date'].min()} to {features_df['date'].max()}")
        
        # Show feature categories
        feature_groups = {
            'USD/TRY': [col for col in features_df.columns if 'usdtry' in col],
            'EUR/TRY': [col for col in features_df.columns if 'eurtry' in col],
            'BIST100': [col for col in features_df.columns if 'bist100' in col],
            'TCMB Rate': [col for col in features_df.columns if 'tcmb' in col],
            'CPI': [col for col in features_df.columns if 'cpi' in col.lower()],
            'M2': [col for col in features_df.columns if 'm2' in col.lower()],
            'Cross/Relative': [col for col in features_df.columns if 'vs_' in col or 'eur_usd' in col],
        }
        
        logger.info("\nFeature Groups:")
        for group_name, cols in feature_groups.items():
            if cols:
                logger.info(f"  {group_name}: {len(cols)} features")
                for col in cols:
                    logger.info(f"    - {col}")
        
        # Check for missing values
        logger.info("\nMissing Values Summary:")
        missing_counts = features_df.isnull().sum()
        missing_counts = missing_counts[missing_counts > 0].sort_values(ascending=False)
        
        if len(missing_counts) > 0:
            logger.info(f"  Found missing values in {len(missing_counts)} columns:")
            for col, count in missing_counts.head(10).items():
                pct = (count / len(features_df)) * 100
                logger.info(f"    {col}: {count} ({pct:.2f}%)")
        else:
            logger.info("  No missing values found!")
        
        # Save to file
        output_file = self.save_features(features_df)
        
        logger.info("\n" + "="*60)
        logger.info("Macro Feature Engineering Complete!")
        logger.info(f"Output: {output_file}")
        logger.info("="*60)
        
        return output_file


def main():
    """Main execution function."""
    engineer = MacroFeatureEngineer()
    engineer.run(fill_method='ffill')


if __name__ == "__main__":
    main()
