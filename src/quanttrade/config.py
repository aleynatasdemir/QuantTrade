"""
QuantTrade - Konfigürasyon Modülü
Bu modül proje genelinde kullanılan ayarları ve yolları yönetir.
"""

import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import toml
from dotenv import load_dotenv


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


def get_evds_settings() -> Dict:
    """
    EVDS ayarlarını döndürür.
    end_date otomatik olarak bugünün tarihine güncellenir.
    """
    settings = load_settings()
    evds_config = settings.get("evds", {})
    
    # end_date'i bugüne güncelle
    evds_config["end_date"] = datetime.now().strftime("%Y-%m-%d")
    
    return evds_config


def get_stocks_settings() -> Dict:
    """
    Hisse senedi ayarlarını döndürür.
    end_date otomatik olarak bugünün tarihine güncellenir.
    """
    settings = load_settings()
    stocks_config = settings.get("stocks", {})
    
    # end_date'i bugüne güncelle
    stocks_config["end_date"] = datetime.now().strftime("%Y-%m-%d")
    
    return stocks_config


def get_stock_symbols() -> list:
    """
    BIST hisse sembolleri listesini config'den getirir.
    
    Returns:
        list: Hisse sembolleri listesi
    """
    stocks_config = get_stocks_settings()
    return stocks_config.get("symbols", [])


def get_stock_date_range() -> tuple:
    """
    Hisse verileri için tarih aralığını config'den getirir.
    end_date otomatik olarak bugüne güncellenir.
    
    Returns:
        tuple: (start_date, end_date) tuple'ı
    """
    stocks_config = get_stocks_settings()  # Otomatik end_date güncellemesi
    start_date = stocks_config.get("start_date", "2020-01-01")
    end_date = stocks_config.get("end_date", datetime.now().strftime("%Y-%m-%d"))
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
