"""
İş Yatırım OHLCV Data Source - BIST hisseleri için günlük OHLCV verisi

Bu modül İş Yatırım sitesinden BIST hisseleri için OHLCV verilerini çeker
ve QuantTrade'in standart formatına dönüştürür.
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import time

try:
    from isyatirimhisse import fetch_stock_data
except ImportError:
    fetch_stock_data = None

from quanttrade.config import ROOT_DIR


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Varsayılan OHLCV veri dizini
DEFAULT_OHLCV_DIR = ROOT_DIR / "data" / "raw" / "ohlcv"


def convert_date_format(date_str: str, from_fmt: str = "%Y-%m-%d", to_fmt: str = "%d-%m-%Y") -> str:
    """
    Tarih formatını dönüştürür.
    
    Args:
        date_str: Tarih string'i
        from_fmt: Giriş formatı (varsayılan: "%Y-%m-%d")
        to_fmt: Çıkış formatı (varsayılan: "%d-%m-%Y")
    
    Returns:
        str: Dönüştürülmüş tarih
    """
    dt = datetime.strptime(date_str, from_fmt)
    return dt.strftime(to_fmt)


def standardize_ohlcv_dataframe(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    İş Yatırım'dan gelen DataFrame'i standart OHLCV formatına çevirici.
    
    Beklenen kolonlar (İş Yatırım verisi):
    - 'Tarih' veya 'Date': Tarih
    - 'Açılış' / 'Open': Açılış fiyatı
    - 'Yüksek' / 'High': En yüksek fiyat
    - 'Düşük' / 'Low': En düşük fiyat
    - 'Kapanış' / 'Close': Kapanış fiyatı
    - 'Hacim' / 'Volume': İşlem hacmi
    
    Çıkış formatı:
    - Index: date (datetime)
    - Kolonlar: ['open', 'high', 'low', 'close', 'volume', 'symbol']
    
    Args:
        df: İş Yatırım'dan gelen DataFrame
        symbol: Hisse senedi kodu
    
    Returns:
        pd.DataFrame: Standart OHLCV formatında DataFrame
    """
    if df is None or df.empty:
        logger.warning(f"Boş DataFrame alındı: {symbol}")
        return pd.DataFrame()
    
    # Orijinal DataFrame'i kopyala
    df = df.copy()
    
    # Kolon adlarını türkçe/ingilizce kombinasyonlarla eşle
    # İş Yatırım API verisi HGDG_ prefix'li kodlar döndürüyor
    column_mapping = {
        # Tarih
        'Tarih': 'date',
        'Date': 'date',
        'DATE': 'date',
        'HGDG_TARIH': 'date',
        # Açılış
        'Açılış': 'open',
        'Open': 'open',
        'OPEN': 'open',
        'HGDG_AOF': 'open',
        # Yüksek
        'Yüksek': 'high',
        'High': 'high',
        'HIGH': 'high',
        'HGDG_MAX': 'high',
        # Düşük
        'Düşük': 'low',
        'Low': 'low',
        'LOW': 'low',
        'HGDG_MIN': 'low',
        # Kapanış
        'Kapanış': 'close',
        'Close': 'close',
        'CLOSE': 'close',
        'HGDG_KAPANIS': 'close',
        # Hacim
        'Hacim': 'volume',
        'Volume': 'volume',
        'VOLUME': 'volume',
        'HGDG_HACIM': 'volume',
    }
    
    # Mevcut kolonları kontrol et ve yeniden adlandır
    rename_dict = {}
    for old_col in df.columns:
        if old_col in column_mapping:
            rename_dict[old_col] = column_mapping[old_col]
    
    if not rename_dict:
        logger.warning(f"Kolon eşlemesi yapılamadı. Mevcut kolonlar: {list(df.columns)}")
    
    df = df.rename(columns=rename_dict)
    
    # Gerekli kolonları kontrol et
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        logger.error(f"Eksik kolonlar ({symbol}): {missing_cols}")
        logger.error(f"Mevcut kolonlar: {list(df.columns)}")
        return pd.DataFrame()
    
    # Tarih sütununu datetime'a çevir
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # NaN tarihli satırları kaldır
    df = df[df['date'].notna()].copy()
    
    if df.empty:
        logger.warning(f"Tarih dönüştürmesi sonrası boş DataFrame: {symbol}")
        return pd.DataFrame()
    
    # Sayısal kolonları float'a çevir
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # NaN değerleri olan satırları kaldır
    df = df[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()
    
    if df.empty:
        logger.warning(f"Numerik dönüştürme sonrası boş DataFrame: {symbol}")
        return pd.DataFrame()
    
    # Symbol kolonu ekle
    df['symbol'] = symbol
    
    # Tarih'e göre sırala
    df = df.sort_values('date').reset_index(drop=True)
    
    # Date'i index yap
    df = df.set_index('date')
    
    # Kolon sırası: open, high, low, close, volume, symbol
    df = df[['open', 'high', 'low', 'close', 'volume', 'symbol']]
    
    logger.info(f"✓ {symbol}: {len(df)} satır, tarih aralığı: {df.index.min().date()} - {df.index.max().date()}")
    
    return df


def fetch_ohlcv_from_isyatirim(
    symbols: List[str],
    start_date: str,  # "YYYY-MM-DD"
    end_date: str,    # "YYYY-MM-DD"
    output_dir: str = None,
    rate_limit_delay: float = 0.5,
) -> None:
    """
    İş Yatırım'dan BIST hisseleri için OHLCV verisi çeker ve parquet dosyalarına kaydeder.
    
    Args:
        symbols: Hisse senedi kodları listesi (örn. ["THYAO", "ASELS", "SISE"])
        start_date: Başlangıç tarihi (ISO formatında: "2020-01-01")
        end_date: Bitiş tarihi (ISO formatında: "2024-12-31")
        output_dir: Çıktı dizini. None ise DEFAULT_OHLCV_DIR kullanılır.
        rate_limit_delay: İstekler arası bekleme süresi (saniye cinsinden)
    
    Raises:
        ImportError: isyatirimhisse paketi kurulu değilse
        ValueError: Tarih formatı yanlışsa
    
    Çıktı:
        CSV dosyaları (parquet değil, daha basit ve hızlı)
        Format:
          - Index: date (datetime)
          - Kolonlar: [open, high, low, close, volume, symbol]
    """
    # İmport kontrolü
    if fetch_stock_data is None:
        raise ImportError(
            "isyatirimhisse paketi kurulu değil. "
            "Lütfen 'pip install isyatirimhisse' komutunu çalıştırın."
        )
    
    # Çıktı dizinini ayarla
    if output_dir is None:
        output_dir = DEFAULT_OHLCV_DIR
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Çıktı dizini: {output_path}")
    
    # Tarih formatını kontrol et ve dönüştür
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Geçersiz tarih formatı. YYYY-MM-DD formatında olmalı. Hata: {e}"
        )
    
    # İş Yatırım formatına çevir (DD-MM-YYYY)
    start_str = start_dt.strftime("%d-%m-%Y")
    end_str = end_dt.strftime("%d-%m-%Y")
    
    logger.info(f"{'='*60}")
    logger.info(f"İş Yatırım OHLCV Veri Çekme Başlatılıyor")
    logger.info(f"{'='*60}")
    logger.info(f"Semboller: {', '.join(symbols)}")
    logger.info(f"Tarih aralığı: {start_date} - {end_date}")
    logger.info(f"İş Yatırım formatı: {start_str} - {end_str}")
    logger.info(f"Rate limit delay: {rate_limit_delay}s")
    logger.info(f"")
    
    # Başarı/hata sayaçları
    success_count = 0
    error_count = 0
    errors = []
    
    # Her sembol için veri çek
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] {symbol} çekiliyor...")
        
        try:
            # İş Yatırım'dan veri çek
            df = fetch_stock_data(
                symbols=symbol,
                start_date=start_str,
                end_date=end_str,
                save_to_excel=False,
            )
            
            # DataFrame'i standardize et
            df_standard = standardize_ohlcv_dataframe(df, symbol)
            
            if df_standard.empty:
                logger.warning(f"✗ {symbol}: Veri işlenemedi")
                error_count += 1
                errors.append((symbol, "Veri işlenemedi"))
            else:
                # CSV dosyasına kaydet
                output_file = output_path / f"{symbol}_ohlcv_isyatirim.csv"
                df_standard.to_csv(output_file, index=True, encoding='utf-8')
                logger.info(f"✓ {symbol}: Kaydedildi ({output_file})")
                success_count += 1
        
        except Exception as e:
            logger.error(f"✗ {symbol}: Hata - {e}")
            error_count += 1
            errors.append((symbol, str(e)))
        
        # Rate limiting (son sembol hariç)
        if i < len(symbols):
            time.sleep(rate_limit_delay)
    
    # Özet rapor
    logger.info(f"")
    logger.info(f"{'='*60}")
    logger.info(f"İş Yatırım OHLCV Veri Çekme Tamamlandı")
    logger.info(f"{'='*60}")
    logger.info(f"✓ Başarılı: {success_count}/{len(symbols)}")
    logger.info(f"✗ Hata: {error_count}/{len(symbols)}")
    
    if errors:
        logger.info(f"")
        logger.info(f"Hata Detayları:")
        for symbol, error_msg in errors:
            logger.info(f"  - {symbol}: {error_msg}")
    
    logger.info(f"")
    logger.info(f"CSV dosyaları: {output_path}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    # Test örneği
    test_symbols = ["THYAO", "ASELS", "SISE"]
    test_start = "2023-01-01"
    test_end = "2024-12-31"
    test_output = "data/raw/ohlcv"
    
    fetch_ohlcv_from_isyatirim(
        symbols=test_symbols,
        start_date=test_start,
        end_date=test_end,
        output_dir=test_output,
        rate_limit_delay=1.0,  # Test için daha yavaş
    )
