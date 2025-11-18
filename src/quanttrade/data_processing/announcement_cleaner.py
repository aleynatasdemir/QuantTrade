"""
KAP Announcement Data Cleaner
Processes raw announcement CSV files and saves cleaned versions.
Focuses on financial report announcements only.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_announcement_date(date_str):
    """
    Parse announcement date string to YYYY-MM-DD HH:MM:SS format.
    Removes timezone information and converts to naive datetime.
    
    Args:
        date_str: Date string in format DD.MM.YYYY HH:MM:SS
        
    Returns:
        str: Date in YYYY-MM-DD HH:MM:SS format or None if parsing fails
    """
    if pd.isna(date_str):
        return None
    
    try:
        # Try DD.MM.YYYY HH:MM:SS format (Turkish standard)
        date_obj = pd.to_datetime(date_str, format='%d.%m.%Y %H:%M:%S')
        return date_obj.strftime('%Y-%m-%d %H:%M:%S')
    except:
        try:
            # Try parsing with pandas default parser
            date_obj = pd.to_datetime(date_str, dayfirst=True)
            # Convert to naive datetime (remove timezone if present)
            if date_obj.tzinfo is not None:
                date_obj = date_obj.tz_localize(None)
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
        except:
            logger.warning(f"Could not parse date: {date_str}")
            return None


def is_financial_report(row):
    """
    Determine if the announcement is a financial report.
    
    Checks ruleType for periodic financial reports:
    - 3 Aylık (Quarterly)
    - 6 Aylık (Semi-annual)
    - 9 Aylık (9-month)
    - Yıllık (Annual)
    
    Also checks summary field for financial keywords if available.
    
    Args:
        row: DataFrame row
        
    Returns:
        bool: True if this is a financial report announcement
    """
    # Check ruleType for periodic reports
    rule_type = str(row.get('ruleType', '')).strip()
    if rule_type in ['3 Aylık', '6 Aylık', '9 Aylık', 'Yıllık']:
        return True
    
    # Check summary for financial keywords (if summary is not empty)
    summary = str(row.get('summary', '')).strip()
    if summary and summary != 'nan' and summary != '':
        financial_keywords = [
            'finansal',
            'finansal rapor',
            'finansal tablo',
            'faaliyet raporu',
            'mali tablo',
            'gelir tablosu',
            'bilanço'
        ]
        summary_lower = summary.lower()
        for keyword in financial_keywords:
            if keyword in summary_lower:
                return True
    
    return False


def process_announcement_file(input_path, output_path):
    """
    Process a single announcement CSV file.
    
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
        
        # Extract symbol from filename
        symbol = input_path.stem.replace('_announcements', '').upper()
        
        # Start with a copy of the original DataFrame
        cleaned_df = df.copy()
        
        # 1. Add symbol column
        cleaned_df.insert(0, 'symbol', symbol)
        
        # 2. Rename/keep index (announcement ID)
        if 'index' in cleaned_df.columns:
            cleaned_df['index'] = cleaned_df['index'].astype(str)
        
        # 3. Parse and convert publishDate to announcement_date
        if 'publishDate' in cleaned_df.columns:
            cleaned_df['announcement_date'] = cleaned_df['publishDate'].apply(parse_announcement_date)
            # Drop original publishDate column (we don't need it anymore)
            # cleaned_df = cleaned_df.drop('publishDate', axis=1)
        else:
            cleaned_df['announcement_date'] = None
        
        # 4. Keep ruleType
        if 'ruleType' in cleaned_df.columns:
            cleaned_df['ruleType'] = cleaned_df['ruleType'].fillna('').astype(str).str.strip()
        else:
            cleaned_df['ruleType'] = ''
        
        # 5. Keep summary
        if 'summary' in cleaned_df.columns:
            cleaned_df['summary'] = cleaned_df['summary'].fillna('').astype(str).str.strip()
        else:
            cleaned_df['summary'] = ''
        
        # 6. Keep url
        if 'url' in cleaned_df.columns:
            cleaned_df['url'] = cleaned_df['url'].fillna('').astype(str).str.strip()
        else:
            cleaned_df['url'] = ''
        
        # 7. Filter for financial reports only
        initial_rows = len(cleaned_df)
        financial_mask = cleaned_df.apply(
            lambda row: is_financial_report(row),
            axis=1
        )
        cleaned_df = cleaned_df[financial_mask].copy()
        filtered_rows = initial_rows - len(cleaned_df)
        
        if filtered_rows > 0:
            logger.info(f"{input_path.name}: Filtered {filtered_rows} non-financial announcements")
        
        # 8. Remove rows where announcement_date is null
        date_null_count = cleaned_df['announcement_date'].isna().sum()
        if date_null_count > 0:
            cleaned_df = cleaned_df.dropna(subset=['announcement_date'])
            logger.info(f"{input_path.name}: Removed {date_null_count} rows with invalid dates")
        
        # 9. Sort by announcement_date (newest first)
        cleaned_df = cleaned_df.sort_values('announcement_date', ascending=False)
        
        # 10. Ensure column order
        column_order = [
            'symbol',
            'index',
            'announcement_date',
            'ruleType',
            'summary',
            'url'
        ]
        cleaned_df = cleaned_df[column_order]
        
        # 11. Reset index
        cleaned_df = cleaned_df.reset_index(drop=True)
        
        # 12. Save to CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_df.to_csv(output_path, index=False)
        
        logger.info(f"✓ Processed {input_path.name} -> {output_path.name} ({len(cleaned_df)} financial reports)")
        
    except Exception as e:
        logger.error(f"Error processing {input_path.name}: {str(e)}")
        raise


def process_all_announcement_files(input_dir, output_dir):
    """
    Process all announcement CSV files in the input directory.
    
    Args:
        input_dir: Path to directory containing raw announcement CSV files
        output_dir: Path to directory for saving cleaned CSV files
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return
    
    # Get all CSV files
    csv_files = sorted(input_path.glob('*_announcements.csv'))
    
    if not csv_files:
        logger.warning(f"No announcement CSV files found in {input_dir}")
        return
    
    logger.info(f"Found {len(csv_files)} announcement files to process")
    logger.info("=" * 60)
    
    success_count = 0
    error_count = 0
    
    for csv_file in csv_files:
        try:
            # Generate output filename
            symbol = csv_file.stem.replace('_announcements', '')
            output_file = output_path / f"{symbol}_announcements_clean.csv"
            
            # Process file
            process_announcement_file(csv_file, output_file)
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
    """Main function to run announcement data cleaning."""
    # Define paths relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    input_dir = project_root / 'data' / 'raw' / 'announcements'
    output_dir = project_root / 'data' / 'processed' / 'announcements'
    
    logger.info("Starting KAP announcement data cleaning process...")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)
    
    process_all_announcement_files(input_dir, output_dir)


if __name__ == '__main__':
    main()
