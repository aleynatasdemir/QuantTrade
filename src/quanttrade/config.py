"""
QuantTrade - Konfigürasyon Modülü
Bu modül proje genelinde kullanılan ayarları ve yolları yönetir.
"""

import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta
import toml
from dotenv import load_dotenv


def get_last_business_day(date: datetime = None) -> datetime:
    """
    Verilen tarihin son iş gününü döndürür.
    Haftasonu ise Cuma'ya geri gider.
    
    Args:
        date: Kontrol edilecek tarih (None ise bugün)
        
    Returns:
        datetime: Son iş günü
    """
    if date is None:
        date = datetime.now()
    
    # Cumartesi (5) veya Pazar (6) ise Cuma'ya geri git
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    
    return date


# Proje kök dizinini belirle
ROOT_DIR = Path(__file__).parent.parent.parent.absolute()
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
MACRO_DATA_DIR = RAW_DATA_DIR / "macro"
LOGS_DIR = ROOT_DIR / "logs"

# .env dosyasını yükle
load_dotenv(ROOT_DIR / ".env")


def get_evds_api_key() -> str:
    """
    EVDS API anahtarını .env dosyasından okur.
    
    Returns:
        str: EVDS API anahtarı
        
    Raises:
        ValueError: API anahtarı .env dosyasında bulunamazsa
    """
    api_key = os.getenv("EVDS_API_KEY")
    
    if not api_key or api_key == "your_evds_api_key_here":
        raise ValueError(
            "EVDS_API_KEY .env dosyasında tanımlanmamış veya geçersiz. "
            "Lütfen .env dosyasına geçerli bir API anahtarı ekleyin. "
            "API anahtarı için: https://evds2.tcmb.gov.tr/"
        )
    
    return api_key


def load_settings() -> Dict[str, Any]:
    """
    config/settings.toml dosyasını okuyup ayarları sözlük olarak döndürür.
    
    Returns:
        Dict[str, Any]: Proje ayarlarını içeren sözlük
        
    Raises:
        FileNotFoundError: settings.toml dosyası bulunamazsa
    """
    settings_path = CONFIG_DIR / "settings.toml"
    
    if not settings_path.exists():
        raise FileNotFoundError(
            f"Ayar dosyası bulunamadı: {settings_path}\n"
            "Lütfen config/settings.toml dosyasının mevcut olduğundan emin olun."
        )
    
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = toml.load(f)
    
    return settings


def get_evds_settings() -> Dict[str, Any]:
    """
    EVDS ile ilgili ayarları getirir.
    
    NOT: end_date otomatik olarak SON İŞ GÜNÜNE ayarlanır.
    Haftasonu ise Cuma'ya geri gider.
    
    Returns:
        Dict[str, Any]: EVDS ayarlarını içeren sözlük
    """
    settings = load_settings()
    evds = settings.get("evds", {})
    # end_date otomatik olarak son iş günü
    evds["end_date"] = get_last_business_day().strftime("%Y-%m-%d")
    return evds


def get_stock_symbols() -> list:
    """
    BIST hisse sembolleri listesini config'den getirir.
    
    Returns:
        list: Hisse sembolleri listesi
    """
    settings = load_settings()
    stocks_config = settings.get("stocks", {})
    return stocks_config.get("symbols", [])


def get_stock_date_range() -> tuple:
    """
    Hisse verileri için tarih aralığını döndürür.
    
    NOT: end_date otomatik olarak SON İŞ GÜNÜNE ayarlanır.
    Haftasonu ise Cuma'ya geri gider.
    
    Returns:
        tuple: (start_date, end_date) tuple'ı
    """
    settings = load_settings()
    stocks_config = settings.get("stocks", {})
    start_date = stocks_config.get("start_date", "2020-01-01")
    # end_date otomatik olarak son iş günü
    end_date = get_last_business_day().strftime("%Y-%m-%d")
    return start_date, end_date


def ensure_directories():
    """
    Gerekli dizinlerin var olduğundan emin olur, yoksa oluşturur.
    """
    directories = [
        CONFIG_DIR,
        DATA_DIR,
        RAW_DATA_DIR,
        MACRO_DATA_DIR,
        LOGS_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# Proje başlatıldığında dizinleri kontrol et
ensure_directories()
