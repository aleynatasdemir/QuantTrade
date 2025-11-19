"""
Mali Tablo Wide-to-Long Format Converter

Bu script data/raw/mali_tablo/*.csv dosyalarını (wide format) 
long format'a dönüştürüp data/processed/mali_tablo/ altına kaydeder.

Input:  data/raw/mali_tablo/{SYMBOL}.csv
        Sütunlar: FINANCIAL_ITEM_CODE, FINANCIAL_ITEM_NAME_TR, FINANCIAL_ITEM_NAME_EN, SYMBOL, 2020/3, 2020/6, ...
        
Output: data/processed/mali_tablo/{SYMBOL}_financials_long.csv
        Sütunlar: symbol, period, item_code, item_name_tr, item_name_en, value
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Proje dizinleri
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_MALI_TABLO_DIR = PROJECT_ROOT / "data" / "raw" / "mali_tablo"
PROCESSED_MALI_TABLO_DIR = PROJECT_ROOT / "data" / "processed" / "mali_tablo"

def convert_wide_to_long(symbol: str) -> pd.DataFrame:
    """
    Mali tablo wide format'ını long format'a dönüştür.
    
    Args:
        symbol: Hisse sembolü (örn: AEFES)
        
    Returns:
        Long format DataFrame
    """
    # CSV oku
    input_file = RAW_MALI_TABLO_DIR / f"{symbol}.csv"
    
    if not input_file.exists():
        logger.warning(f"  {symbol}: Dosya bulunamadı ({input_file})")
        return None
    
    df = pd.read_csv(input_file)
    
    logger.info(f"  {symbol}: {len(df)} satır, {len(df.columns)} sütun")
    
    # Metadata sütunları
    metadata_cols = ['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN', 'SYMBOL']
    
    # Kontrol et - metadata sütunları var mı
    missing_cols = [col for col in metadata_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"  {symbol}: Eksik sütunlar: {missing_cols}")
        return None
    
    # Period sütunları (2020/3, 2020/6 vs)
    period_cols = [col for col in df.columns if col not in metadata_cols]
    
    logger.debug(f"    Period sütunları ({len(period_cols)}): {period_cols[:5]}...")
    
    # Wide-to-long dönüştürme
    # id_vars: metadata (değişmeyecek sütunlar)
    # value_vars: period sütunları (yığılacak sütunlar)
    long_df = pd.melt(
        df,
        id_vars=metadata_cols,
        value_vars=period_cols,
        var_name='period',
        value_name='value'
    )
    
    # Sütun adlarını küçültün
    long_df.columns = [col.lower() for col in long_df.columns]
    
    # symbol sütununu kontrol et ve düzelt
    # Raw CSV'de symbol redundant olabilir, index olarak kullanalım
    long_df['symbol'] = symbol
    
    # Veri tipi dönüştürmeleri
    # item_code ve period text olarak kalsın
    # value numeric yapıl
    long_df['value'] = pd.to_numeric(long_df['value'], errors='coerce')
    
    # NaN kontrolü
    nan_count = long_df['value'].isna().sum()
    if nan_count > 0:
        logger.debug(f"    {nan_count} NaN değer bulundu")
        # NaN'ları drop et
        long_df = long_df.dropna(subset=['value'])
    
    # Sütun sırası
    long_df = long_df[['symbol', 'period', 'financial_item_code', 'financial_item_name_tr', 'financial_item_name_en', 'value']]
    
    # Sütun adlarını standartlaştır
    long_df.columns = ['symbol', 'period', 'item_code', 'item_name_tr', 'item_name_en', 'value']
    
    return long_df


def main():
    """Ana işlem fonksiyonu."""
    
    logger.info("="*80)
    logger.info("MALİ TABLO WIDE-TO-LONG CONVERTER")
    logger.info("="*80)
    
    # Output klasörü oluştur
    PROCESSED_MALI_TABLO_DIR.mkdir(parents=True, exist_ok=True)
    
    # Raw mali tablo dosyalarını bul
    csv_files = list(RAW_MALI_TABLO_DIR.glob("*.csv"))
    
    if not csv_files:
        logger.error(f"Mali tablo dosyası bulunamadı: {RAW_MALI_TABLO_DIR}")
        sys.exit(1)
    
    # Her hisse için dönüştürme yap
    successful = 0
    failed = 0
    
    for i, csv_file in enumerate(sorted(csv_files), 1):
        symbol = csv_file.stem  # Dosya adından sembolü çıkar
        
        logger.info(f"[{i}/{len(csv_files)}] {symbol} dönüştürülüyor...")
        
        try:
            # Dönüştür
            long_df = convert_wide_to_long(symbol)
            
            if long_df is None or len(long_df) == 0:
                logger.warning(f"  {symbol}: Sonuç boş, atlanıyor")
                failed += 1
                continue
            
            # Kaydet
            output_file = PROCESSED_MALI_TABLO_DIR / f"{symbol}_financials_long.csv"
            long_df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"  ✓ {symbol}: {len(long_df):,} satır → {output_file.name}")
            successful += 1
            
        except Exception as e:
            logger.error(f"  ✗ {symbol}: Hata - {e}")
            failed += 1
            continue
    
    # Özet
    logger.info("\n" + "="*80)
    logger.info(f"ÖZET: {successful}/{len(csv_files)} başarılı, {failed} başarısız")
    logger.info(f"Çıktı klasörü: {PROCESSED_MALI_TABLO_DIR}")
    logger.info("="*80)


if __name__ == "__main__":
    main()
