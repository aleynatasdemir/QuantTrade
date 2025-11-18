"""
Dividend Data Cleaner
Processes raw dividend CSV files and saves cleaned versions.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_numeric_value(value):
    """
    Clean numeric values by removing formatting characters.
    
    Examples:
        "%10,5" -> 10.5
        "1.234.567" -> 1234567.0
        "10,5" -> 10.5
    
    Args:
        value: String or numeric value to clean
        
    Returns:
        float: Cleaned numeric value or NaN if conversion fails
    """
    if pd.isna(value):
        return np.nan
    
    if isinstance(value, (int, float)):
        return float(value)
    
    # Convert to string and strip whitespace
    value_str = str(value).strip()
    
    if value_str == '' or value_str == '-':
        return np.nan
    
    try:
        # Remove % sign if present
        value_str = value_str.replace('%', '')
        
        # Check if value uses comma as decimal separator (Turkish format)
        # e.g., "10,5" or "1.234,56"
        if ',' in value_str and '.' in value_str:
            # Both present: dot is thousand separator, comma is decimal
            # e.g., "1.234,56" -> "1234.56"
            value_str = value_str.replace('.', '').replace(',', '.')
        elif ',' in value_str:
            # Only comma: it's the decimal separator
            # e.g., "10,5" -> "10.5"
            value_str = value_str.replace(',', '.')
        elif '.' in value_str:
            # Only dot: check if it's thousand separator or decimal
            # If more than one dot, they're thousand separators
            dot_count = value_str.count('.')
            if dot_count > 1:
                value_str = value_str.replace('.', '')
            # Otherwise, assume it's a decimal separator
        
        return float(value_str)
    except (ValueError, AttributeError):
        return np.nan


def parse_date(date_str):
    """
    Parse date string to YYYY-MM-DD format.
    
    Args:
        date_str: Date string in format DD.MM.YYYY
        
    Returns:
        str: Date in YYYY-MM-DD format or None if parsing fails
    """
    if pd.isna(date_str):
        return None
    
    try:
        # Try DD.MM.YYYY format (Turkish standard)
        date_obj = pd.to_datetime(date_str, format='%d.%m.%Y', dayfirst=True)
        return date_obj.strftime('%Y-%m-%d')
    except:
        try:
            # Try other common formats
            date_obj = pd.to_datetime(date_str, dayfirst=True)
            return date_obj.strftime('%Y-%m-%d')
        except:
            logger.warning(f"Could not parse date: {date_str}")
            return None


def process_dividend_file(input_path, output_path):
    """
    Process a single dividend CSV file.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path to output CSV file
    """
    try:
        # Read CSV
        df = pd.read_csv(input_path)
        
        if df.empty:
            logger.warning(f"Empty file: {input_path.name}")
            return
        
        # Create output DataFrame
        cleaned_df = pd.DataFrame()
        
        # 1. Symbol standardization
        if 'Kod' in df.columns:
            cleaned_df['symbol'] = df['Kod'].astype(str).str.strip().str.upper()
        else:
            # Extract symbol from filename
            symbol = input_path.stem.replace('_dividends', '').upper()
            cleaned_df['symbol'] = symbol
        
        # 2. Date formatting
        if 'Dagitim_Tarihi' in df.columns:
            cleaned_df['ex_date'] = df['Dagitim_Tarihi'].apply(parse_date)
        else:
            cleaned_df['ex_date'] = None
        
        # 3. Clean numeric columns
        numeric_columns = {
            'Temettu_Verim': 'dividend_yield_pct',
            'Hisse_Basi_TL': 'dividend_per_share',
            'Brut_Oran': 'gross_pct',
            'Net_Oran': 'net_pct',
            'Toplam_Temettu_TL': 'total_dividend_tl',
            'Dagitma_Orani': 'payout_ratio_pct'
        }
        
        for old_col, new_col in numeric_columns.items():
            if old_col in df.columns:
                cleaned_df[new_col] = df[old_col].apply(clean_numeric_value)
            else:
                cleaned_df[new_col] = np.nan
        
        # 4. Ensure column order
        column_order = [
            'symbol',
            'ex_date',
            'dividend_yield_pct',
            'dividend_per_share',
            'gross_pct',
            'net_pct',
            'total_dividend_tl',
            'payout_ratio_pct'
        ]
        
        # Reorder columns
        cleaned_df = cleaned_df[column_order]
        
        # 5. Remove rows where ex_date is null
        initial_rows = len(cleaned_df)
        cleaned_df = cleaned_df.dropna(subset=['ex_date'])
        removed_rows = initial_rows - len(cleaned_df)
        
        if removed_rows > 0:
            logger.info(f"{input_path.name}: Removed {removed_rows} rows with invalid dates")
        
        # 6. Sort by date (newest first)
        cleaned_df = cleaned_df.sort_values('ex_date', ascending=False)
        
        # 7. Save to CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_df.to_csv(output_path, index=False)
        
        logger.info(f"✓ Processed {input_path.name} -> {output_path.name} ({len(cleaned_df)} rows)")
        
    except Exception as e:
        logger.error(f"Error processing {input_path.name}: {str(e)}")
        raise


def process_all_dividend_files(input_dir, output_dir):
    """
    Process all dividend CSV files in the input directory.
    
    Args:
        input_dir: Path to directory containing raw dividend CSV files
        output_dir: Path to directory for saving cleaned CSV files
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return
    
    # Get all CSV files
    csv_files = sorted(input_path.glob('*_dividends.csv'))
    
    if not csv_files:
        logger.warning(f"No dividend CSV files found in {input_dir}")
        return
    
    logger.info(f"Found {len(csv_files)} dividend files to process")
    logger.info("=" * 60)
    
    success_count = 0
    error_count = 0
    
    for csv_file in csv_files:
        try:
            # Generate output filename
            symbol = csv_file.stem.replace('_dividends', '')
            output_file = output_path / f"{symbol}_dividends_clean.csv"
            
            # Process file
            process_dividend_file(csv_file, output_file)
            success_count += 1
            
        except Exception as e:
            logger.error(f"Failed to process {csv_file.name}: {str(e)}")
            error_count += 1
    
    logger.info("=" * 60)
    logger.info(f"Processing complete!")
    logger.info(f"✓ Successfully processed: {success_count} files")
    if error_count > 0:
        logger.info(f"✗ Failed: {error_count} files")


def main():
    """Main function to run dividend data cleaning."""
    # Define paths relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    input_dir = project_root / 'data' / 'raw' / 'dividend'
    output_dir = project_root / 'data' / 'processed' / 'dividend'
    
    logger.info("Starting dividend data cleaning process...")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)
    
    process_all_dividend_files(input_dir, output_dir)


if __name__ == '__main__':
    main()
