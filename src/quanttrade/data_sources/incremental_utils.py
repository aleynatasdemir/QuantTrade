"""
Incremental Data Utils - Artımsal veri çekme için yardımcı fonksiyonlar

Bu modül, tüm data source scriptlerinin ortak kullanacağı incremental logic
fonksiyonlarını içerir.
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Union

logger = logging.getLogger(__name__)


def is_weekend(date: datetime) -> bool:
    """Verilen tarih haftasonu mu kontrol eder."""
    return date.weekday() >= 5  # 5=Cumartesi, 6=Pazar


def get_last_business_day(date: datetime = None) -> datetime:
    """
    En son iş gününü döndürür.
    Eğer bugün haftasonu ise Cuma'ya geri gider.
    
    Args:
        date: Kontrol edilecek tarih (None ise bugün)
        
    Returns:
        datetime: Son iş günü
    """
    if date is None:
        date = datetime.now()
    
    # Sadece tarihi al (saat bilgisini sıfırla)
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Haftasonu ise geriye git
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    
    return date


def is_data_up_to_date(last_date: datetime, target_date: str = None) -> bool:
    """
    Veri güncel mi kontrol eder. Haftasonlarını dikkate alır.
    
    Args:
        last_date: Verideki son tarih
        target_date: Hedef tarih string (YYYY-MM-DD formatında, None ise bugün)
        
    Returns:
        bool: Veri güncel mi
    """
    if last_date is None:
        return False
    
    # Hedef tarihi belirle
    if target_date:
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except:
            target = datetime.now()
    else:
        target = datetime.now()
    
    # Hedef tarihi son iş gününe ayarla
    target = get_last_business_day(target)
    
    # last_date'i de datetime'a çevir (eğer timestamp ise)
    if isinstance(last_date, pd.Timestamp):
        last_date = last_date.to_pydatetime()
    
    # Sadece tarih karşılaştır (saat bilgisi olmadan)
    last_date_only = last_date.replace(hour=0, minute=0, second=0, microsecond=0)
    target_only = target.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return last_date_only >= target_only


def get_last_date_from_csv(
    file_path: Path,
    date_column: str,
    date_format: Optional[str] = None,
    parse_dates: bool = True
) -> Optional[datetime]:
    """
    CSV dosyasından en son tarihi okur.
    
    Args:
        file_path: CSV dosya yolu
        date_column: Tarih kolonu adı
        date_format: Tarih parse formatı (None ise otomatik)
        parse_dates: Tarihi parse et
        
    Returns:
        datetime veya None (dosya yoksa/bozuksa)
    """
    if not file_path.exists():
        logger.info(f"Dosya bulunamadı, full çekim yapılacak: {file_path}")
        return None
    
    try:
        # Sadece tarih kolonunu oku (performans için)
        df = pd.read_csv(file_path, usecols=[date_column], parse_dates=[date_column] if parse_dates else False)
        
        if df.empty:
            logger.warning(f"Dosya boş: {file_path}")
            return None
        
        # Tarih kolonunu datetime'a çevir
        if not parse_dates:
            if date_format:
                df[date_column] = pd.to_datetime(df[date_column], format=date_format, errors='coerce')
            else:
                df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        
        # NaT değerlerini çıkar
        df = df[df[date_column].notna()]
        
        if df.empty:
            logger.warning(f"Geçerli tarih bulunamadı: {file_path}")
            return None
        
        last_date = df[date_column].max()
        
        # pandas Timestamp ise datetime'a çevir
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.to_pydatetime()
        
        logger.info(f"Son tarih bulundu: {last_date.strftime('%Y-%m-%d')} ({file_path.name})")
        return last_date
        
    except Exception as e:
        logger.warning(f"Dosya okunamadı, full çekim yapılacak: {file_path} - Hata: {e}")
        return None


def get_last_date_from_parquet(
    file_path: Path,
    date_column: str
) -> Optional[datetime]:
    """
    Parquet dosyasından en son tarihi okur.
    
    Args:
        file_path: Parquet dosya yolu
        date_column: Tarih kolonu adı
        
    Returns:
        datetime veya None
    """
    if not file_path.exists():
        logger.info(f"Dosya bulunamadı, full çekim yapılacak: {file_path}")
        return None
    
    try:
        df = pd.read_parquet(file_path, columns=[date_column])
        
        if df.empty:
            return None
        
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df[df[date_column].notna()]
        
        if df.empty:
            return None
        
        last_date = df[date_column].max()
        
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.to_pydatetime()
        
        logger.info(f"Son tarih bulundu: {last_date.strftime('%Y-%m-%d')} ({file_path.name})")
        return last_date
        
    except Exception as e:
        logger.warning(f"Parquet okunamadı: {file_path} - Hata: {e}")
        return None


def calculate_incremental_date_range(
    last_date: Optional[datetime],
    config_start_date: str,
    config_end_date: str,
    date_format: str = "%Y-%m-%d"
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Incremental çekim için tarih aralığını hesaplar.
    Haftasonlarını dikkate alır (borsa kapalı).
    
    Args:
        last_date: Mevcut verinin son tarihi (None ise full çekim)
        config_start_date: Config'teki başlangıç tarihi
        config_end_date: Config'teki bitiş tarihi
        date_format: Tarih formatı
        
    Returns:
        (new_start, new_end, is_incremental) tuple'ı
        - is_incremental=False ise full çekim yapılmalı
        - new_start > new_end ise veri güncel demektir (None, None, True döner)
    """
    try:
        end_dt = datetime.strptime(config_end_date, date_format)
    except ValueError:
        # Farklı format dene
        try:
            end_dt = datetime.strptime(config_end_date, "%d-%m-%Y")
        except ValueError:
            end_dt = datetime.now()
    
    # Full çekim gerekiyor
    if last_date is None:
        logger.info("İlk çekim - full aralık kullanılacak")
        return config_start_date, config_end_date, False
    
    # Hedef tarihi son iş gününe ayarla (haftasonu ise Cuma'ya)
    target_dt = get_last_business_day(end_dt)
    
    # last_date'i de normalize et
    last_date_normalized = last_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Veri zaten güncel mi? (son iş günü ile karşılaştır)
    if last_date_normalized >= target_dt:
        logger.info(f"Veri güncel! Son tarih: {last_date.strftime('%Y-%m-%d')}, Hedef iş günü: {target_dt.strftime('%Y-%m-%d')}")
        return None, None, True
    
    # Incremental başlangıç: son tarih + 1 gün
    new_start_dt = last_date + timedelta(days=1)
    
    # Başlangıç haftasonu ise Pazartesi'ye ilerle
    while new_start_dt.weekday() >= 5:
        new_start_dt += timedelta(days=1)
    
    # Yine de kontrol et
    if new_start_dt > target_dt:
        logger.info(f"Veri güncel! Sonraki iş günü: {new_start_dt.strftime('%Y-%m-%d')}, Hedef: {target_dt.strftime('%Y-%m-%d')}")
        return None, None, True
    
    new_start = new_start_dt.strftime(date_format)
    new_end = config_end_date
    
    logger.info(f"Incremental aralık: {new_start} -> {new_end}")
    return new_start, new_end, True


def append_and_deduplicate(
    old_df: pd.DataFrame,
    new_df: pd.DataFrame,
    unique_columns: List[str],
    sort_columns: Optional[List[str]] = None,
    keep: str = 'last'
) -> pd.DataFrame:
    """
    Eski ve yeni DataFrame'leri birleştirir, duplikatları temizler.
    
    Args:
        old_df: Mevcut veri
        new_df: Yeni çekilen veri
        unique_columns: Benzersizlik için kullanılacak kolonlar
        sort_columns: Sıralama için kullanılacak kolonlar
        keep: Duplikat durumunda hangisi tutulsun ('first', 'last')
        
    Returns:
        Birleştirilmiş ve temizlenmiş DataFrame
    """
    if old_df.empty:
        combined = new_df.copy()
    elif new_df.empty:
        combined = old_df.copy()
    else:
        combined = pd.concat([old_df, new_df], ignore_index=True)
    
    if combined.empty:
        return combined
    
    # Duplikatları temizle
    combined = combined.drop_duplicates(subset=unique_columns, keep=keep)
    
    # Sırala
    if sort_columns:
        combined = combined.sort_values(sort_columns).reset_index(drop=True)
    
    return combined


def safe_read_csv(
    file_path: Path,
    **kwargs
) -> pd.DataFrame:
    """
    CSV dosyasını güvenli şekilde okur.
    
    Args:
        file_path: Dosya yolu
        **kwargs: pd.read_csv'ye geçilecek parametreler
        
    Returns:
        DataFrame (dosya yoksa/bozuksa boş DataFrame)
    """
    if not file_path.exists():
        return pd.DataFrame()
    
    try:
        return pd.read_csv(file_path, **kwargs)
    except Exception as e:
        logger.warning(f"CSV okunamadı: {file_path} - Hata: {e}")
        return pd.DataFrame()


def is_data_up_to_date(
    file_path: Path,
    date_column: str,
    end_date: str,
    tolerance_days: int = 1
) -> bool:
    """
    Verinin güncel olup olmadığını kontrol eder.
    
    Args:
        file_path: Dosya yolu
        date_column: Tarih kolonu
        end_date: Hedef bitiş tarihi
        tolerance_days: Tolerans günü (hafta sonu vs için)
        
    Returns:
        True ise veri güncel
    """
    last_date = get_last_date_from_csv(file_path, date_column)
    
    if last_date is None:
        return False
    
    try:
        target_date = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        target_date = datetime.now()
    
    diff = (target_date - last_date).days
    
    return diff <= tolerance_days


def get_symbols_needing_update(
    symbols: List[str],
    output_dir: Path,
    file_pattern: str,
    date_column: str,
    end_date: str,
    tolerance_days: int = 1
) -> Tuple[List[str], List[str]]:
    """
    Güncelleme gereken sembolleri belirler.
    
    Args:
        symbols: Sembol listesi
        output_dir: Çıktı dizini
        file_pattern: Dosya adı pattern'i (örn: "{symbol}_ohlcv.csv")
        date_column: Tarih kolonu
        end_date: Hedef bitiş tarihi
        tolerance_days: Tolerans günü
        
    Returns:
        (needs_update, up_to_date) tuple'ı
    """
    needs_update = []
    up_to_date = []
    
    for symbol in symbols:
        file_name = file_pattern.format(symbol=symbol)
        file_path = output_dir / file_name
        
        if is_data_up_to_date(file_path, date_column, end_date, tolerance_days):
            up_to_date.append(symbol)
        else:
            needs_update.append(symbol)
    
    if up_to_date:
        logger.info(f"{len(up_to_date)} sembol zaten güncel, atlanacak")
    
    return needs_update, up_to_date
