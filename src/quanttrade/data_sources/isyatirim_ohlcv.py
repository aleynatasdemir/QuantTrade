"""
İş Yatırım OHLCV Data Source - BIST hisseleri için günlük OHLCV verisi (INCREMENTAL MOD)

Bu modül İş Yatırım sitesinden BIST hisseleri için OHLCV verilerini çeker
ve QuantTrade'in standart formatına dönüştürür.

INCREMENTAL LOGIC:
- Her sembol için mevcut CSV dosyasına bakar
- Son tarihten itibaren sadece eksik günleri çeker
- Eski veriyle birleştirir, duplikatları temizler
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import time
import random

try:
    from isyatirimhisse import fetch_stock_data
except ImportError:
    fetch_stock_data = None

from quanttrade.config import ROOT_DIR
from quanttrade.data_sources.incremental_utils import (
    calculate_incremental_date_range,
    append_and_deduplicate,
)


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Varsayılan OHLCV veri dizini
DEFAULT_OHLCV_DIR = ROOT_DIR / "data" / "raw" / "ohlcv"


def convert_date_format(date_str: str, from_fmt: str = "%Y-%m-%d", to_fmt: str = "%d-%m-%Y") -> str:
    dt = datetime.strptime(date_str, from_fmt)
    return dt.strftime(to_fmt)


def standardize_ohlcv_dataframe(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """OHLCV DataFrame'ini standart formata dönüştürür."""
    if df is None or df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    
    column_mapping = {
        'Tarih': 'date', 'Date': 'date', 'DATE': 'date', 'HGDG_TARIH': 'date',
        'Açılış': 'open', 'Open': 'open', 'OPEN': 'open', 'HGDG_AOF': 'open',
        'Yüksek': 'high', 'High': 'high', 'HIGH': 'high', 'HGDG_MAX': 'high',
        'Düşük': 'low', 'Low': 'low', 'LOW': 'low', 'HGDG_MIN': 'low',
        'Kapanış': 'close', 'Close': 'close', 'CLOSE': 'close', 'HGDG_KAPANIS': 'close',
        'Hacim': 'volume', 'Volume': 'volume', 'VOLUME': 'volume', 'HGDG_HACIM': 'volume',
    }
    
    rename_dict = {}
    for old_col in df.columns:
        if old_col in column_mapping:
            rename_dict[old_col] = column_mapping[old_col]
    
    df = df.rename(columns=rename_dict)
    
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        return pd.DataFrame()
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df[df['date'].notna()].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()
    
    if df.empty:
        return pd.DataFrame()
    
    df['symbol'] = symbol
    df = df.sort_values('date').reset_index(drop=True)
    
    return df


def get_incremental_range_for_symbol(
    symbol: str,
    output_dir: Path,
    config_start_date: str,
    config_end_date: str
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Bir sembol için incremental tarih aralığını hesaplar.
    
    Returns:
        (start_date, end_date, is_up_to_date) tuple'ı
        - is_up_to_date=True ve start_date=None ise veri güncel
    """
    file_path = output_dir / f"{symbol}_ohlcv_isyatirim.csv"
    
    if not file_path.exists():
        logger.info(f"{symbol}: Dosya yok, full çekim yapılacak")
        return config_start_date, config_end_date, False
    
    try:
        # Index'li CSV'yi oku (date index olarak kaydedilmiş)
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        
        if df.empty:
            logger.info(f"{symbol}: Dosya boş, full çekim yapılacak")
            return config_start_date, config_end_date, False
        
        # Index'ten son tarihi al
        last_date = df.index.max()
        
        if pd.isna(last_date):
            return config_start_date, config_end_date, False
        
        # datetime'a çevir
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.to_pydatetime()
        
        # Incremental aralık hesapla
        return calculate_incremental_date_range(
            last_date, config_start_date, config_end_date
        )
        
    except Exception as e:
        logger.warning(f"{symbol}: Dosya okunamadı ({e}), full çekim yapılacak")
        return config_start_date, config_end_date, False


def fetch_ohlcv_incremental(
    symbol: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    rate_limit_delay: float = 2.0,
    max_retries: int = 3,
    base_wait: int = 60
) -> Tuple[bool, int]:
    """
    Tek bir sembol için incremental OHLCV verisi çeker.
    
    Returns:
        (success, row_count) tuple'ı
    """
    if fetch_stock_data is None:
        raise ImportError("isyatirimhisse paketi kurulu değil.")
    
    file_path = output_dir / f"{symbol}_ohlcv_isyatirim.csv"
    
    # Mevcut veriyi oku (varsa)
    old_df = pd.DataFrame()
    if file_path.exists():
        try:
            old_df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            old_df = old_df.reset_index()
            if old_df.columns[0] != 'date':
                old_df.rename(columns={old_df.columns[0]: 'date'}, inplace=True)
        except Exception as e:
            logger.warning(f"{symbol}: Mevcut dosya okunamadı: {e}")
            old_df = pd.DataFrame()
    
    # Tarih formatını İş Yatırım API için dönüştür
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        start_dt = datetime.strptime(start_date, "%d-%m-%Y")
        end_dt = datetime.strptime(end_date, "%d-%m-%Y")
    
    start_str = start_dt.strftime("%d-%m-%Y")
    end_str = end_dt.strftime("%d-%m-%Y")
    
    # API'den veri çek (retry mekanizmasıyla)
    success = False
    new_df = pd.DataFrame()
    last_error = None
    
    for attempt in range(max_retries):
        try:
            df = fetch_stock_data(
                symbols=symbol,
                start_date=start_str,
                end_date=end_str,
                save_to_excel=False,
            )
            
            if df is None or df.empty:
                raise ValueError("Boş veri döndü (Olası Rate Limit)")
            
            new_df = standardize_ohlcv_dataframe(df, symbol)
            
            if new_df.empty:
                raise ValueError("Veri standardize edilemedi")
            
            success = True
            break
            
        except Exception as e:
            last_error = str(e)
            wait_time = base_wait + (attempt * 10) + random.uniform(1, 5)
            
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ {symbol} Hata (Deneme {attempt+1}/{max_retries}): {e}")
                logger.warning(f"⏳ {wait_time:.1f}s bekleniyor...")
                time.sleep(wait_time)
            else:
                logger.error(f"✗ {symbol}: BAŞARISIZ! (Son Hata: {e})")
    
    if not success:
        return False, 0
    
    # Eski ve yeni veriyi birleştir
    if not old_df.empty and not new_df.empty:
        # date kolonunu datetime yap
        if 'date' in old_df.columns:
            old_df['date'] = pd.to_datetime(old_df['date'], errors='coerce')
        if 'date' in new_df.columns:
            new_df['date'] = pd.to_datetime(new_df['date'], errors='coerce')
        
        combined_df = append_and_deduplicate(
            old_df, new_df,
            unique_columns=['date'],
            sort_columns=['date'],
            keep='last'
        )
    elif new_df.empty:
        combined_df = old_df
    else:
        combined_df = new_df
    
    if combined_df.empty:
        logger.warning(f"{symbol}: Birleştirilmiş veri boş!")
        return False, 0
    
    # Kaydet (date'i index olarak)
    combined_df = combined_df.sort_values('date').reset_index(drop=True)
    combined_df = combined_df.set_index('date')
    combined_df = combined_df[['open', 'high', 'low', 'close', 'volume', 'symbol']]
    
    combined_df.to_csv(file_path, index=True, encoding='utf-8')
    
    return True, len(combined_df)


def fetch_ohlcv_from_isyatirim(
    symbols: List[str],
    start_date: str,
    end_date: str,
    output_dir: str = None,
    rate_limit_delay: float = 2.0,
) -> None:
    """
    İş Yatırım'dan OHLCV verilerini INCREMENTAL olarak çeker.
    
    Her sembol için:
    1. Mevcut dosyaya bakar
    2. Son tarihten sonraki verileri çeker
    3. Eski veriyle birleştirir
    """
    if fetch_stock_data is None:
        raise ImportError("isyatirimhisse paketi kurulu değil.")
    
    if output_dir is None:
        output_dir = DEFAULT_OHLCV_DIR
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
<<<<<<< HEAD
    logger.info(f"{'='*60}")
    logger.info(f"İş Yatırım OHLCV Veri Çekme (INCREMENTAL MOD)")
    logger.info(f"Semboller: {len(symbols)} adet")
    logger.info(f"Config aralığı: {start_date} -> {end_date}")
    logger.info(f"{'='*60}")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    errors = []
=======
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Geçersiz tarih formatı: {e}")
    
    start_str = start_dt.strftime("%d-%m-%Y")
    end_str = end_dt.strftime("%d-%m-%Y")
    
    
    logger.info(f"{'='*60}")
    logger.info(f"İş Yatırım OHLCV Veri Çekme")
    logger.info(f"Toplam: {len(symbols)} sembol")
    logger.info(f"{'='*60}")
    
    successful = 0
    failed = 0
    BATCH_SIZE = 20  # Her 20 hissede bir log
>>>>>>> f253addf5f28e99f0d3a026638901b029d9ebe09
    
    MAX_RETRIES = 3
    BASE_WAIT = 60
    
<<<<<<< HEAD
    for i, symbol in enumerate(symbols, 1):
        # Incremental aralık hesapla
        new_start, new_end, is_incremental = get_incremental_range_for_symbol(
            symbol, output_path, start_date, end_date
        )
=======
    for idx, symbol in enumerate(symbols, 1):
        # Batch progress log (her 20'de bir veya son hisse)
        if idx % BATCH_SIZE == 1 or idx == len(symbols):
            end_idx = min(idx + BATCH_SIZE - 1, len(symbols))
            logger.info(f"📊 OHLCV {idx}-{end_idx}/{len(symbols)} işleniyor...")
>>>>>>> f253addf5f28e99f0d3a026638901b029d9ebe09
        
        # Veri güncel mi?
        if new_start is None and is_incremental:
            logger.info(f"[{i}/{len(symbols)}] {symbol}: ✓ Güncel, atlanıyor")
            skip_count += 1
            continue
        
<<<<<<< HEAD
        logger.info(f"[{i}/{len(symbols)}] {symbol} çekiliyor ({new_start} -> {new_end})...")
        
        # Veri çek
        success, row_count = fetch_ohlcv_incremental(
            symbol=symbol,
            start_date=new_start,
            end_date=new_end,
            output_dir=output_path,
            rate_limit_delay=rate_limit_delay,
            max_retries=MAX_RETRIES,
            base_wait=BASE_WAIT
        )
        
        if success:
            logger.info(f"✓ {symbol}: OK ({row_count} satır)")
            success_count += 1
        else:
            error_count += 1
            errors.append(symbol)
        
        # Rate limiting
        if i < len(symbols):
            time.sleep(rate_limit_delay + random.uniform(1.0, 3.0))
    
    logger.info(f"{'='*60}")
    logger.info(f"Tamamlandı. Başarılı: {success_count} | Atlanan (güncel): {skip_count} | Hata: {error_count}")
    if errors:
        logger.info(f"Hatalı Hisseler: {', '.join(errors)}")
=======
        for attempt in range(MAX_RETRIES):
            try:
                df = fetch_stock_data(
                    symbols=symbol,
                    start_date=start_str,
                    end_date=end_str,
                    save_to_excel=False,
                )
                
                if df is None or df.empty:
                    raise ValueError("Boş veri")
                
                df_standard = standardize_ohlcv_dataframe(df, symbol)
                
                if df_standard.empty:
                    raise ValueError("Veri standardize edilemedi")
                
                # Save
                output_file = output_path / f"{symbol}_ohlcv_isyatirim.csv"
                df_standard.to_csv(output_file, index=True, encoding='utf-8')
                
                success = True
                successful += 1
                break
            
            except Exception as e:
                last_error = str(e)[:50]
                wait_time = BASE_WAIT + (attempt * 10) + random.uniform(1, 5)
                
                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait_time)
                else:
                    # Sadece hatalı olanları logla
                    logger.error(f"❌ {symbol} - {last_error}")
        
        if not success:
            failed += 1
        
        # Rate limit between stocks
        if idx < len(symbols):
            time.sleep(rate_limit_delay + random.uniform(1.0, 3.0))
    
    logger.info(f"{'='*60}")
    logger.info(f"✅ Tamamlandı: {successful} başarılı, {failed} hatalı")
>>>>>>> f253addf5f28e99f0d3a026638901b029d9ebe09
