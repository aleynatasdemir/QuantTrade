"""
EVDS Makro Veri Temizleme Pipeline

Görev:
- Tarih işleme ve normalizasyon
- Kolon tiplerini float'a çevir
- Hatalı değerleri NaN olarak işle
- Çıktıyı processed klasörüne kaydet
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path

# Project setup
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "macro"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "macro"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILE = RAW_DIR / "evds_macro_daily.csv"
OUTPUT_FILE = PROCESSED_DIR / "evds_macro_daily_clean.csv"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_macro_data(input_path: Path, output_path: Path):
    """
    EVDS makro verisini temizle ve normalize et.
    
    Args:
        input_path: Girdi CSV dosyası
        output_path: Çıktı CSV dosyası
    """
    logger.info("=" * 70)
    logger.info("EVDS MAKRO VERİ TEMIZLEME")
    logger.info("=" * 70)
    
    # 1. Dosyayı oku
    logger.info(f"\n📖 Okunuyor: {input_path}")
    
    if not input_path.exists():
        logger.error(f"❌ Dosya bulunamadı: {input_path}")
        return
    
    try:
        df = pd.read_csv(input_path)
        logger.info(f"   ✓ {len(df)} satır, {len(df.columns)} kolon okundu")
    except Exception as e:
        logger.error(f"❌ Dosya okuma hatası: {e}")
        return
    
    # 2. Kolon isimlerini normalize et (lowercase)
    logger.info("\n🏷 Kolon isimleri normalize ediliyor...")
    df.columns = [col.lower().strip() for col in df.columns]
    logger.info(f"   ✓ Kolonlar: {', '.join(df.columns)}")
    
    # 3. Tarih işleme
    logger.info("\n📅 Tarih işleme...")
    
    # Tarih sütununu bul
    date_cols = [col for col in df.columns if 'date' in col or 'tarih' in col]
    
    if not date_cols:
        logger.error("❌ Tarih sütunu bulunamadı")
        return
    
    date_col = date_cols[0]
    logger.info(f"   ✓ Tarih sütunu: {date_col}")
    
    # Tarih sütununu datetime'a çevir
    try:
        df[date_col] = pd.to_datetime(df[date_col], format='%Y-%m-%d', errors='coerce')
        logger.info(f"   ✓ Tarih formatı: YYYY-MM-DD")
    except Exception as e:
        logger.warning(f"   ⚠ Tarih çevirme hatası: {e}, alternative format deneniyor...")
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            logger.info(f"   ✓ Tarih otomatik olarak çevrildi")
        except Exception as e2:
            logger.error(f"❌ Tarih çevrilemedi: {e2}")
            return
    
    # Hatalı tarihleri kontrol et
    null_dates = df[date_col].isna().sum()
    if null_dates > 0:
        logger.warning(f"   ⚠ {null_dates} hatalı tarih bulundu (NaN olarak işlendi)")
    
    # Tarih sütunu adını standardize et
    df = df.rename(columns={date_col: 'date'})
    
    # Tarihe göre sırala
    df = df.sort_values('date').reset_index(drop=True)
    logger.info(f"   ✓ Tarihe göre sıralandı: {df['date'].min()} - {df['date'].max()}")
    
    # 4. Makro kolon tipi dönüşümü
    logger.info("\n🔢 Makro kolonlar float'a çevriliyor...")
    
    macro_cols = [col for col in df.columns if col != 'date']
    
    for col in macro_cols:
        if col in df.columns:
            # Özet göster
            non_null_count = df[col].notna().sum()
            logger.info(f"   {col}:")
            
            # String tipindeyse, binlik ayırıcı vs. temizle
            if df[col].dtype == 'object':
                # Binlik ayırıcı vs. karakterleri kaldır
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = df[col].astype(str).str.replace(' ', '', regex=False)
            
            # Float'a çevir
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            null_count = df[col].isna().sum()
            logger.info(f"      ✓ Float çevirme tamamlandı")
            logger.info(f"      ✓ Veri: {non_null_count} adet (NaN: {null_count})")
    
    # 5. Kolon sırası: date ilk, sonra diğerleri alfabetik
    logger.info("\n📋 Kolon sırası düzenleniyor...")
    
    cols = ['date'] + sorted([col for col in df.columns if col != 'date'])
    df = df[cols]
    logger.info(f"   ✓ Sıra: {', '.join(cols[:3])}...")
    
    # 6. İstatistikler
    logger.info("\n📊 VERİ İSTATİSTİKLERİ:")
    logger.info(f"   Toplam satır: {len(df)}")
    logger.info(f"   Toplam kolon: {len(df.columns)}")
    logger.info(f"   Tarih aralığı: {df['date'].min()} - {df['date'].max()}")
    
    logger.info(f"\n   Kolon bazında boş değerler:")
    for col in df.columns:
        null_pct = (df[col].isna().sum() / len(df) * 100)
        logger.info(f"      {col}: {null_pct:.1f}% (n={df[col].isna().sum()})")
    
    # 7. Çıktıya kaydet
    logger.info(f"\n💾 Kaydediliyor: {output_path}")
    
    try:
        df.to_csv(output_path, index=False, encoding='utf-8')
        logger.info(f"   ✓ Başarıyla kaydedildi")
    except Exception as e:
        logger.error(f"❌ Dosya yazma hatası: {e}")
        return
    
    # 8. Özet
    logger.info("\n" + "=" * 70)
    logger.info("ÖZET")
    logger.info("=" * 70)
    logger.info(f"Girdi: {input_path}")
    logger.info(f"Çıktı: {output_path}")
    logger.info(f"Satırlar: {len(df)}")
    logger.info(f"Kolonlar: {len(df.columns)}")
    logger.info("=" * 70)
    
    # 9. İlk birkaç satır göster
    logger.info(f"\n📋 İlk 5 satır:")
    logger.info(f"\n{df.head().to_string()}")
    
    return df


if __name__ == "__main__":
    df = clean_macro_data(INPUT_FILE, OUTPUT_FILE)
    
    if df is not None:
        logger.info("\n✓ İşlem tamamlandı!")
    else:
        logger.error("\n❌ İşlem başarısız!")
