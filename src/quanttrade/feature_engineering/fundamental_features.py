"""
Fundamental Feature Engineering Agent (A2.2) - ROBUST & FIXED

This module processes financial statements from data/processed/mali_tablo/
and aligns them with announcement dates from data/processed/announcements/
to create period-level fundamental features.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Optional, Tuple
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
    
    # HIBRIT MAPPING (BANKA + SANAYİ)
    ITEM_MAPPING = {
        'net_profit': ['NET DÖNEM KARI', 'NET KAR', 'DÖNEM NET KARI', 'DÖNEM KARI', 'NET DÖNEM KARI/ZARARI'],
        'net_sales': ['NET SATIŞLAR', 'HASILAT', 'SATIŞ GELİRLERİ', 'I. FAİZ GELİRLERİ', 'FAİZ GELİRLERİ', 'KAR PAYI GELİRLERİ'],
        'total_assets': ['TOPLAM VARLIKLAR', 'AKTİF TOPLAMI', 'VARLIKLAR TOPLAMI'],
        'total_liabilities': ['TOPLAM YÜKÜMLÜLÜKLER', 'TOPLAM BORÇLAR', 'YÜKÜMLÜLÜKLER TOPLAMI'],
        'total_equity': ['ÖZKAYNAKLAR', 'SERMAYE', 'XVI. ÖZKAYNAKLAR', 'ANA ORTAKLIĞA AİT ÖZKAYNAKLAR'],
        'current_liabilities': ['KISA VADELİ YÜKÜMLÜLÜKLER', 'KISA VADELİ BORÇLAR'],
        'current_assets': ['DÖNEN VARLIKLAR'],
        'long_term_liabilities': ['UZUN VADELİ YÜKÜMLÜLÜKLER', 'UZUN VADELİ BORÇLAR'],
        'revenue': ['HASILAT', 'NET SATIŞLAR', 'BRÜT SATIŞLAR', 'SATIŞ GELİRLERİ', 'SATIŞ GELİRLERİ (NET)'],
        'operating_profit': ['FAALİYET KARI (ZARARI)', 'ESAS FAALİYET KARI', 'NET FAALİYET KAR/ZARARI', 'FAALİYET KARI'],
        'ebitda': ['FAVÖK', 'EBITDA'],
        'gross_profit': ['BRÜT KAR', 'BRÜT SATIŞ KARI', 'BRÜT KAR (ZARAR)', 'III. NET FAİZ GELİRİ'],
        'depreciation': ['AMORTİSMAN GİDERLERİ', 'AMORTİSMAN & İTFA PAYLARI', 'AMORTİSMAN VE İTFA PAYLARI'],
    }
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            self.base_path = Path(__file__).parent.parent.parent.parent
        else:
            self.base_path = Path(base_path)
            
        self.mali_tablo_path = self.base_path / 'data' / 'processed' / 'mali_tablo'
        self.announcements_path = self.base_path / 'data' / 'processed' / 'announcements'
        self.output_path = self.base_path / 'data' / 'features' / 'fundamental'
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    def _find_item_value(self, df: pd.DataFrame, period: str, feature_names: list) -> Optional[float]:
        period_data = df[df['period'] == period]
        for name in feature_names:
            matches = period_data[
                period_data['item_name_tr'].str.contains(name, case=False, na=False)
            ]
            if not matches.empty:
                return matches.iloc[0]['value']
        return None
    
    def _pivot_financials(self, df: pd.DataFrame) -> pd.DataFrame:
        periods = df['period'].unique()
        symbol = df['symbol'].iloc[0]
        
        rows = []
        for period in periods:
            row = {'symbol': symbol, 'period': period}
            for feature_name, turkish_names in self.ITEM_MAPPING.items():
                value = self._find_item_value(df, period, turkish_names)
                row[feature_name] = value
            rows.append(row)
        
        wide_df = pd.DataFrame(rows)
        
        # CRITICAL FIX: Force all value columns to numeric (float)
        # This converts None/Objects to NaN and integers to floats, preventing object-division errors.
        for col in wide_df.columns:
            if col not in ['symbol', 'period']:
                wide_df[col] = pd.to_numeric(wide_df[col], errors='coerce')
                
        return wide_df
    
    def _calculate_ratios(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        # 1. Fix Total Liabilities (Assets - Equity)
        if 'total_liabilities' not in result.columns:
            result['total_liabilities'] = np.nan
            
        mask_missing_liab = (
            result['total_liabilities'].isna() & 
            result['total_assets'].notna() & 
            result['total_equity'].notna()
        )
        if mask_missing_liab.any():
            result.loc[mask_missing_liab, 'total_liabilities'] = (
                result.loc[mask_missing_liab, 'total_assets'] - 
                result.loc[mask_missing_liab, 'total_equity']
            )

        # 2. Fix Total Debt
        if 'total_debt' not in result.columns or result['total_debt'].isna().all():
            # Initialize with 0
            result['total_debt'] = 0.0
            # Add current if exists
            if 'current_liabilities' in result.columns:
                result['total_debt'] += result['current_liabilities'].fillna(0)
            # Add long term if exists
            if 'long_term_liabilities' in result.columns:
                result['total_debt'] += result['long_term_liabilities'].fillna(0)
            
            # If result is still 0 but we have total_liabilities, use that (for Banks)
            mask_zero = (result['total_debt'] == 0) & (result['total_liabilities'].notna())
            result.loc[mask_zero, 'total_debt'] = result.loc[mask_zero, 'total_liabilities']
        
        # 3. Fix EBITDA
        if 'ebitda' not in result.columns or result['ebitda'].isna().all():
            op_profit = result['operating_profit'].fillna(0) if 'operating_profit' in result.columns else 0
            depreciation = result['depreciation'].fillna(0) if 'depreciation' in result.columns else 0
            result['ebitda'] = op_profit + depreciation
        
        # --- SAFE DIVISION BLOCK (Prevents ZeroDivisionError) ---
        def safe_calc_ratio(df, num_col, den_col, ratio_name):
            df[ratio_name] = np.nan
            # Only calculate where denominator exists and is NOT zero
            if num_col in df.columns and den_col in df.columns:
                mask = (df[den_col].notna()) & (df[den_col] != 0) & (df[num_col].notna())
                if mask.any():
                    df.loc[mask, ratio_name] = df.loc[mask, num_col] / df.loc[mask, den_col]

        # Apply safe calculations
        safe_calc_ratio(result, 'net_profit', 'total_equity', 'roe')
        safe_calc_ratio(result, 'net_profit', 'total_assets', 'roa')
        safe_calc_ratio(result, 'net_profit', 'net_sales', 'net_margin')
        safe_calc_ratio(result, 'total_debt', 'total_equity', 'debt_to_equity')
        safe_calc_ratio(result, 'current_assets', 'current_liabilities', 'current_ratio')
        
        return result
    
    def _calculate_yoy_growth(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result['period_dt'] = pd.to_datetime(result['period'], format='%Y/%m')
        result = result.sort_values('period_dt')
        
        result['quarter'] = result['period_dt'].dt.quarter
        result['year'] = result['period_dt'].dt.year
        
        result['revenue_growth_yoy'] = np.nan
        result['profit_growth_yoy'] = np.nan
        
        # Loop is safe here as it's row-by-row
        for idx in result.index:
            current_quarter = result.loc[idx, 'quarter']
            current_year = result.loc[idx, 'year']
            
            prev = result[
                (result['quarter'] == current_quarter) & 
                (result['year'] == current_year - 1)
            ]
            
            if not prev.empty:
                # Revenue Growth
                prev_sales = prev.iloc[0]['net_sales']
                curr_sales = result.loc[idx, 'net_sales']
                if pd.notna(prev_sales) and pd.notna(curr_sales) and prev_sales != 0:
                    result.loc[idx, 'revenue_growth_yoy'] = (curr_sales - prev_sales) / prev_sales
                
                # Profit Growth
                prev_profit = prev.iloc[0]['net_profit']
                curr_profit = result.loc[idx, 'net_profit']
                if pd.notna(prev_profit) and pd.notna(curr_profit) and prev_profit != 0:
                    result.loc[idx, 'profit_growth_yoy'] = (curr_profit - prev_profit) / prev_profit
        
        result = result.drop(['period_dt', 'quarter', 'year'], axis=1)
        return result
    
    def _match_announcement_dates(self, financial_df: pd.DataFrame, announcements_df: pd.DataFrame) -> pd.DataFrame:
        result = financial_df.copy()
        result['announcement_date'] = pd.NaT
        result['period_end'] = pd.to_datetime(result['period'], format='%Y/%m') + pd.offsets.MonthEnd(0)
        announcements_df['announcement_date'] = pd.to_datetime(announcements_df['announcement_date'])
        
        for idx in result.index:
            period_end = result.loc[idx, 'period_end']
            candidates = announcements_df[
                (announcements_df['announcement_date'] >= period_end) &
                (announcements_df['announcement_date'] <= period_end + pd.Timedelta(days=120))
            ].sort_values('announcement_date')
            
            if not candidates.empty:
                result.loc[idx, 'announcement_date'] = candidates.iloc[0]['announcement_date']
            else:
                # Fallback: closest future date
                future = announcements_df[announcements_df['announcement_date'] >= period_end].sort_values('announcement_date')
                if not future.empty:
                    result.loc[idx, 'announcement_date'] = future.iloc[0]['announcement_date']
        
        result = result.drop('period_end', axis=1)
        return result
    
    def process_symbol(self, symbol: str) -> bool:
        try:
            logger.info(f"Processing {symbol}...")
            
            f_file = self.mali_tablo_path / f"{symbol}_financials_long.csv"
            a_file = self.announcements_path / f"{symbol}_announcements_clean.csv"
            
            if not f_file.exists() or not a_file.exists():
                logger.warning(f"Files missing for {symbol}")
                return False
            
            financial_df = pd.read_csv(f_file)
            announcements_df = pd.read_csv(a_file)
            
            wide_df = self._pivot_financials(financial_df)
            if wide_df.empty: return False
            
            ratio_df = self._calculate_ratios(wide_df)
            growth_df = self._calculate_yoy_growth(ratio_df)
            final_df = self._match_announcement_dates(growth_df, announcements_df)
            
            # Select final columns
            ratio_cols = ['roe', 'roa', 'net_margin', 'debt_to_equity', 'current_ratio', 'revenue_growth_yoy', 'profit_growth_yoy']
            meta_cols = ['symbol', 'period', 'announcement_date']
            other_cols = [c for c in final_df.columns if c not in ratio_cols + meta_cols]
            
            final_cols = meta_cols + ratio_cols + other_cols
            final_cols = [c for c in final_cols if c in final_df.columns]
            
            output_file = self.output_path / f"{symbol}_fundamental_period_features.csv"
            final_df[final_cols].to_csv(output_file, index=False)
            
            logger.info(f"  ✓ Saved {len(final_df)} periods")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}", exc_info=True)
            return False
    
    def process_all_symbols(self):
        files = list(self.mali_tablo_path.glob("*_financials_long.csv"))
        symbols = sorted([f.stem.replace('_financials_long', '') for f in files])
        logger.info(f"Found {len(symbols)} symbols")
        
        for sym in symbols:
            self.process_symbol(sym)

if __name__ == "__main__":
    FundamentalFeatureEngineer().process_all_symbols()