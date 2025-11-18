"""
Small utility to convert a parquet file to an Excel .xlsx for easy viewing.
Defaults to the project's master parquet file: data/master/master_df.parquet
Writes to: data/master/master_df.xlsx

Usage:
    python3 parquet_to_xlsx.py
    python3 parquet_to_xlsx.py /path/to/input.parquet /path/to/output.xlsx
"""

import sys
from pathlib import Path
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def convert_parquet_to_xlsx(input_path: Path, output_path: Path):
    logger.info(f"Reading parquet: {input_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input parquet not found: {input_path}")

    # Read parquet
    df = pd.read_parquet(input_path)

    # Ensure output dir exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing Excel: {output_path}")
    try:
        df.to_excel(output_path, index=False, engine='openpyxl')
    except Exception as e:
        logger.error("Failed to write Excel. If you see an ImportError for openpyxl, install it with: pip install openpyxl")
        raise

    logger.info(f"Done. Rows: {len(df):,}, Columns: {len(df.columns)}")


if __name__ == '__main__':
    # Default paths (relative to repo root)
    repo_root = Path(__file__).parent.parent.parent.parent
    default_input = repo_root / 'data' / 'master' / 'master_df.parquet'
    default_output = repo_root / 'data' / 'master' / 'master_df.xlsx'

    if len(sys.argv) >= 3:
        input_p = Path(sys.argv[1])
        output_p = Path(sys.argv[2])
    elif len(sys.argv) == 2:
        input_p = Path(sys.argv[1])
        output_p = default_output
    else:
        input_p = default_input
        output_p = default_output

    try:
        convert_parquet_to_xlsx(input_p, output_p)
    except Exception as exc:
        logger.error(str(exc))
        sys.exit(1)
