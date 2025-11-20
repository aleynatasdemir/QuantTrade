"""
Master DataFrame Builder Agent (A2.4)

This module combines all feature sets into a single master dataframe:
- Price & Technical features (symbol + date level)
- Macro features (date level)
- Fundamental features (symbol + period + announcement_date level)

The critical rule: Fundamental data is only available AFTER announcement_date.

Input:
    - data/features/price/*_price_features.csv
    - data/features/fundamental/*_fundamental_period_features.csv
    - data/features/macro/macro_features_daily.csv

Output:
    - data/master/master_df.parquet
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, List, Optional
import warnings

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MasterDataFrameBuilder:
    """
    Builds the final master dataframe combining all feature sets.
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize the master dataframe builder.
        
        Args:
            base_path: Base path to the QuantTrade project
        """
        if base_path is None:
            # Auto-detect base path
            self.base_path = Path(__file__).parent.parent.parent.parent
        else:
            self.base_path = Path(base_path)
            
        self.price_features_path = self.base_path / 'data' / 'features' / 'price'
        self.fundamental_features_path = self.base_path / 'data' / 'features' / 'fundamental'
        self.macro_features_path = self.base_path / 'data' / 'features' / 'macro'
        self.output_path = self.base_path / 'data' / 'master'
        
        # Create output directory
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Base path: {self.base_path}")
        logger.info(f"Price features path: {self.price_features_path}")
        logger.info(f"Fundamental features path: {self.fundamental_features_path}")
        logger.info(f"Macro features path: {self.macro_features_path}")
        logger.info(f"Output path: {self.output_path}")
        
        # Column categorization
        self.id_columns = ['symbol', 'date']
        self.target_columns = []
        self.feature_columns = []
    
    # ====================================================
    # LOADERS
    # ====================================================
    
    def load_macro_features(self) -> pd.DataFrame:
        """
        Load macro features.
        
        Returns:
            DataFrame with macro features
        """
        logger.info("Loading macro features...")
        
        macro_file = self.macro_features_path / 'macro_features_daily.csv'
        
        if not macro_file.exists():
            raise FileNotFoundError(f"Macro features file not found: {macro_file}")
        
        df = pd.read_csv(macro_file)
        df['date'] = pd.to_datetime(df['date'])
        
        # Rename columns with macro_ prefix (except date)
        rename_dict = {col: f'macro_{col}' for col in df.columns if col != 'date'}
        df = df.rename(columns=rename_dict)
        
        logger.info(f"  Loaded {len(df)} days of macro features")
        logger.info(f"  Columns: {len(df.columns)}")
        
        return df
    
    def load_price_features(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Load price features for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DataFrame with price features or None if not found
        """
        price_file = self.price_features_path / f"{symbol}_price_features.csv"
        
        if not price_file.exists():
            logger.warning(f"  Price features not found for {symbol}")
            return None
        
        df = pd.read_csv(price_file)
        df['date'] = pd.to_datetime(df['date'])
        
        # Identify target columns (future_return and y_ columns)
        target_cols = [col for col in df.columns if col.startswith('future_return_') or col.startswith('y_')]
        
        # Rename non-target, non-id columns with price_ prefix
        rename_dict = {}
        for col in df.columns:
            if col not in ['symbol', 'date'] and col not in target_cols:
                rename_dict[col] = f'price_{col}'
        
        df = df.rename(columns=rename_dict)
        
        return df
    
    def load_fundamental_features(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Load fundamental features for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DataFrame with fundamental features or None if not found
        """
        fund_file = self.fundamental_features_path / f"{symbol}_fundamental_period_features.csv"
        
        if not fund_file.exists():
            logger.warning(f"  Fundamental features not found for {symbol}")
            return None
        
        df = pd.read_csv(fund_file)
        df['announcement_date'] = pd.to_datetime(df['announcement_date'])
        
        # Rename columns with fund_ prefix (except symbol, period, announcement_date)
        rename_dict = {}
        for col in df.columns:
            if col not in ['symbol', 'period', 'announcement_date']:
                rename_dict[col] = f'fund_{col}'
        
        df = df.rename(columns=rename_dict)
        
        return df
    
    # ====================================================
    # MERGE HELPERS
    # ====================================================
    
    def merge_fundamental_with_asof(
        self,
        price_df: pd.DataFrame,
        fundamental_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge fundamental features with price data using asof merge.
        
        Critical rule: For a trading date d, only use fundamental data where
        announcement_date <= d. Use the most recent announcement.
        
        Args:
            price_df: Price features DataFrame (symbol + date)
            fundamental_df: Fundamental features DataFrame (symbol + period + announcement_date)
            
        Returns:
            Merged DataFrame
        """
        # Ensure data is sorted
        price_df = price_df.sort_values('date').reset_index(drop=True)
        fundamental_df = fundamental_df.sort_values('announcement_date').reset_index(drop=True)
        
        merged = pd.merge_asof(
            price_df,
            fundamental_df,
            left_on='date',
            right_on='announcement_date',
            by='symbol',
            direction='backward',
            suffixes=('', '_fund')
        )
        
        return merged
    
    def process_symbol(
        self,
        symbol: str,
        macro_df: pd.DataFrame
    ) -> Optional[pd.DataFrame]:
        """
        Process a single symbol: merge price, macro, and fundamental features.
        
        Args:
            symbol: Stock symbol to process
            macro_df: Macro features DataFrame
            
        Returns:
            Merged DataFrame or None if failed
        """
        logger.info(f"Processing {symbol}...")
        
        # Load price features
        price_df = self.load_price_features(symbol)
        if price_df is None:
            return None
        
        logger.info(f"  Price data: {len(price_df)} days")
        
        # Merge with macro features
        logger.info(f"  Merging with macro features...")
        merged = pd.merge(
            price_df,
            macro_df,
            on='date',
            how='left'
        )
        
        logger.info(f"  After macro merge: {len(merged)} rows")
        
        # Load and merge fundamental features
        fundamental_df = self.load_fundamental_features(symbol)
        
        if fundamental_df is not None:
            logger.info(f"  Fundamental data: {len(fundamental_df)} periods")
            logger.info(f"  Merging with fundamental features (asof)...")
            
            merged = self.merge_fundamental_with_asof(merged, fundamental_df)
            
            # Count how many rows have fundamental data
            fund_cols = [col for col in merged.columns if col.startswith('fund_')]
            if fund_cols:
                non_null_count = merged[fund_cols[0]].notna().sum()
                logger.info(f"  Rows with fundamental data: {non_null_count}/{len(merged)}")
        else:
            logger.info(f"  No fundamental features available")
        
        return merged
    
    # ====================================================
    # ALPHA / MARKET FUTURE RETURN
    # ====================================================
    
    def add_market_alpha(
        self,
        df: pd.DataFrame,
        horizon: int = 120
    ) -> pd.DataFrame:
        """
        Add:
        - market_future_return_{horizon}d (BIST100'e göre)
        - alpha_{horizon}d = future_return_{horizon}d - market_future_return_{horizon}d
        """
        fut_col = f"future_return_{horizon}d"
        mkt_col = "macro_bist100"
        mkt_fut_col = f"market_future_return_{horizon}d"
        alpha_col = f"alpha_{horizon}d"
        
        if mkt_col not in df.columns:
            logger.warning(f"{mkt_col} not found in master_df. Skipping alpha computation.")
            return df
        
        if fut_col not in df.columns:
            logger.warning(f"{fut_col} not found in master_df. Skipping alpha computation.")
            return df
        
        logger.info(f"\nComputing market future return ({mkt_fut_col}) and alpha ({alpha_col})...")
        
        # BIST100 future return date-level (aynı tarih için tüm satırlar aynı değeri alacak)
        mkt_series = (
            df
            .groupby('date')[mkt_col]
            .first()
            .sort_index()
        )
        
        mkt_future = mkt_series.shift(-horizon) / mkt_series - 1.0
        mkt_future = mkt_future.rename(mkt_fut_col).reset_index()
        
        # merge back
        df = df.merge(mkt_future, on='date', how='left')
        
        # alpha = hisse future_return - market_future_return
        df[alpha_col] = df[fut_col] - df[mkt_fut_col]
        
        logger.info(f"  Added columns: {mkt_fut_col}, {alpha_col}")
        
        return df
    
    # ====================================================
    # MASTER BUILD
    # ====================================================
    
    def build_master_dataframe(
        self,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Build the complete master dataframe for all symbols.
        
        Args:
            min_date: Minimum date to include (format: 'YYYY-MM-DD')
            max_date: Maximum date to include (format: 'YYYY-MM-DD')
            
        Returns:
            Master DataFrame
        """
        logger.info("="*60)
        logger.info("Building Master DataFrame (A2.4)")
        logger.info("="*60)
        
        # Load macro features once (shared across all symbols)
        macro_df = self.load_macro_features()
        
        # Get list of symbols from price features
        price_files = list(self.price_features_path.glob("*_price_features.csv"))
        symbols = sorted([f.stem.replace('_price_features', '') for f in price_files])
        
        logger.info(f"\nFound {len(symbols)} symbols to process")
        
        # Process each symbol and collect results
        all_data = []
        successful = 0
        failed = 0
        
        for symbol in symbols:
            try:
                symbol_df = self.process_symbol(symbol, macro_df)
                
                if symbol_df is not None:
                    all_data.append(symbol_df)
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {str(e)}")
                failed += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing complete: {successful} successful, {failed} failed")
        logger.info(f"{'='*60}")
        
        # Concatenate all symbol data
        logger.info("\nCombining all symbols...")
        master_df = pd.concat(all_data, ignore_index=True)
        
        # Apply date filters if specified
        if min_date:
            min_date_dt = pd.to_datetime(min_date)
            before = len(master_df)
            master_df = master_df[master_df['date'] >= min_date_dt]
            logger.info(f"  Filtered by min_date {min_date}: {before} -> {len(master_df)} rows")
        
        if max_date:
            max_date_dt = pd.to_datetime(max_date)
            before = len(master_df)
            master_df = master_df[master_df['date'] <= max_date_dt]
            logger.info(f"  Filtered by max_date {max_date}: {before} -> {len(master_df)} rows")
        
        # Sort by symbol and date
        master_df = master_df.sort_values(['symbol', 'date']).reset_index(drop=True)
        
        return master_df
    
    # ====================================================
    # COLUMN CATEGORIZATION
    # ====================================================
    
    def categorize_columns(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        Categorize columns into ID, features, and targets.
        
        Args:
            df: Master DataFrame
            
        Returns:
            Dictionary with column categories
        """
        all_columns = df.columns.tolist()
        
        # ID columns
        id_cols = ['symbol', 'date']
        
        # Target columns (future-looking variables, alpha dahil)
        target_cols = [
            col for col in all_columns 
            if col.startswith('future_return_')
            or col.startswith('y_')
            or col.startswith('alpha_')
        ]
        
        # Metadata columns (not features, not targets)
        metadata_cols = ['period', 'announcement_date']
        
        # Feature columns (everything else)
        feature_cols = [
            col for col in all_columns 
            if col not in id_cols + target_cols + metadata_cols
        ]
        
        return {
            'id_columns': id_cols,
            'feature_columns': feature_cols,
            'target_columns': target_cols,
            'metadata_columns': [col for col in metadata_cols if col in all_columns]
        }
    
    # ====================================================
    # SPLIT / SUMMARY / SAVE
    # ====================================================
    
    def add_dataset_split(
        self,
        df: pd.DataFrame,
        train_end_date: str,
        valid_end_date: str
    ) -> pd.DataFrame:
        """
        Add dataset split column (train/valid/test) based on dates.
        
        Args:
            df: Master DataFrame
            train_end_date: End date for training set (format: 'YYYY-MM-DD')
            valid_end_date: End date for validation set (format: 'YYYY-MM-DD')
            
        Returns:
            DataFrame with dataset_split column added
        """
        df = df.copy()
        
        train_end = pd.to_datetime(train_end_date)
        valid_end = pd.to_datetime(valid_end_date)
        
        conditions = [
            df['date'] <= train_end,
            (df['date'] > train_end) & (df['date'] <= valid_end),
            df['date'] > valid_end
        ]
        
        choices = ['train', 'valid', 'test']
        
        df['dataset_split'] = np.select(conditions, choices, default='test')
        
        # Log split statistics
        split_counts = df['dataset_split'].value_counts().sort_index()
        logger.info("\nDataset Split Statistics:")
        for split, count in split_counts.items():
            pct = (count / len(df)) * 100
            logger.info(f"  {split}: {count} rows ({pct:.2f}%)")
        
        return df
    
    def generate_summary_report(
        self,
        df: pd.DataFrame,
        column_categories: Dict[str, List[str]]
    ) -> None:
        """
        Generate and log a summary report of the master dataframe.
        
        Args:
            df: Master DataFrame
            column_categories: Dictionary of column categories
        """
        logger.info("\n" + "="*60)
        logger.info("MASTER DATAFRAME SUMMARY")
        logger.info("="*60)
        
        # Basic statistics
        logger.info(f"\nBasic Statistics:")
        logger.info(f"  Total rows: {len(df):,}")
        logger.info(f"  Total columns: {len(df.columns)}")
        logger.info(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        
        # Date range
        logger.info(f"\nDate Range:")
        logger.info(f"  Start: {df['date'].min()}")
        logger.info(f"  End: {df['date'].max()}")
        logger.info(f"  Days: {(df['date'].max() - df['date'].min()).days}")
        
        # Symbol statistics
        logger.info(f"\nSymbol Statistics:")
        logger.info(f"  Unique symbols: {df['symbol'].nunique()}")
        symbol_counts = df['symbol'].value_counts()
        logger.info(
            f"  Rows per symbol: "
            f"min={symbol_counts.min()}, "
            f"max={symbol_counts.max()}, "
            f"mean={symbol_counts.mean():.0f}"
        )
        
        # Column categories
        logger.info(f"\nColumn Categories:")
        for category, cols in column_categories.items():
            logger.info(f"  {category}: {len(cols)}")
        
        # Feature groups
        logger.info(f"\nFeature Groups:")
        feature_cols = column_categories['feature_columns']
        
        price_features = [c for c in feature_cols if c.startswith('price_')]
        macro_features = [c for c in feature_cols if c.startswith('macro_')]
        fund_features = [c for c in feature_cols if c.startswith('fund_')]
        
        logger.info(f"  Price & Technical: {len(price_features)}")
        logger.info(f"  Macro: {len(macro_features)}")
        logger.info(f"  Fundamental: {len(fund_features)}")
        
        # Missing value analysis
        logger.info(f"\nMissing Values (Top 10):")
        missing_counts = df.isnull().sum()
        missing_counts = missing_counts[missing_counts > 0].sort_values(ascending=False)
        
        if len(missing_counts) > 0:
            for col, count in missing_counts.head(10).items():
                pct = (count / len(df)) * 100
                logger.info(f"  {col}: {count:,} ({pct:.2f}%)")
        else:
            logger.info("  No missing values!")
        
        # Target variable summary
        if column_categories['target_columns']:
            logger.info(f"\nTarget Variables:")
            for target_col in column_categories['target_columns']:
                if target_col in df.columns:
                    non_null = df[target_col].notna().sum()
                    logger.info(f"  {target_col}: {non_null:,} non-null values")
        
        logger.info("\n" + "="*60)
    
    def save_master_dataframe(
        self,
        df: pd.DataFrame,
        column_categories: Dict[str, List[str]],
        format: str = 'parquet'
    ) -> str:
        """
        Save the master dataframe and metadata.
        
        Args:
            df: Master DataFrame
            column_categories: Dictionary of column categories
            format: Output format ('parquet' or 'feather')
            
        Returns:
            Path to saved file
        """
        logger.info(f"\nSaving master dataframe as {format}...")
        
        if format == 'parquet':
            output_file = self.output_path / 'master_df.parquet'
            df.to_parquet(output_file, index=False, engine='pyarrow')
        elif format == 'feather':
            output_file = self.output_path / 'master_df.feather'
            df.to_feather(output_file)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"  ✓ Saved to {output_file}")
        
        # Save metadata (column categories)
        metadata_file = self.output_path / 'master_df_metadata.json'
        
        import json
        with open(metadata_file, 'w') as f:
            json.dump(column_categories, f, indent=2)
        
        logger.info(f"  ✓ Saved metadata to {metadata_file}")
        
        return str(output_file)
    
    # ====================================================
    # RUN
    # ====================================================
    
    def run(
        self,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        train_end_date: Optional[str] = '2023-12-31',
        valid_end_date: Optional[str] = '2024-12-31',
        output_format: str = 'parquet'
    ) -> str:
        """
        Execute the complete master dataframe building pipeline.
        
        Args:
            min_date: Minimum date to include
            max_date: Maximum date to include
            train_end_date: End date for training set
            valid_end_date: End date for validation set
            output_format: Output format ('parquet' or 'feather')
            
        Returns:
            Path to output file
        """
        # Build master dataframe
        master_df = self.build_master_dataframe(min_date=min_date, max_date=max_date)
        
        # Add market future return + alpha (120d)
        master_df = self.add_market_alpha(master_df, horizon=120)
        master_df = self.add_market_alpha(master_df, horizon=60)
        master_df = self.add_market_alpha(master_df, horizon=90)
        
        # Add dataset split
        if train_end_date and valid_end_date:
            logger.info("\nAdding dataset split...")
            master_df = self.add_dataset_split(master_df, train_end_date, valid_end_date)
        
        # Categorize columns
        column_categories = self.categorize_columns(master_df)
        
        # Generate summary report
        self.generate_summary_report(master_df, column_categories)
        
        # Save to file
        output_file = self.save_master_dataframe(
            master_df,
            column_categories,
            format=output_format
        )
        
        logger.info("\n" + "="*60)
        logger.info("Master DataFrame Building Complete!")
        logger.info(f"Output: {output_file}")
        logger.info("="*60)
        
        return output_file


def main():
    """Main execution function."""
    builder = MasterDataFrameBuilder()
    
    # Build master dataframe
    # Filter to data from 2020 onwards
    builder.run(
        min_date='2020-01-01',
        max_date=None,
        train_end_date='2023-12-31',
        valid_end_date='2024-12-31',
        output_format='parquet'
    )


if __name__ == "__main__":
    main()
