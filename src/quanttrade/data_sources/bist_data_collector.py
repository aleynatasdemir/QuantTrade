"""
BIST Hisse Veri Toplama Pipeline
isyatirimhisse kütüphanesi kullanarak BIST'teki tüm hisseler için kapsamlı veri toplar.

Gerekli kurulum:
pip install isyatirimhisse pandas numpy

Kullanım:
python bist_data_collector.py
"""

import pandas as pd
import numpy as np
import logging
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from isyatirimhisse import fetch_stock_data, fetch_financials
except ImportError:
    print("HATA: isyatirimhisse kütüphanesi bulunamadı!")
    print("Lütfen şu komutu çalıştırın: pip install isyatirimhisse")
    exit(1)

# Proje config'inden import
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "financials"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from quanttrade.config import get_stock_symbols, get_stock_date_range
except ImportError:
    print("UYARI: quanttrade.config import edilemedi, varsayılan değerler kullanılacak")
    get_stock_symbols = None
    get_stock_date_range = None


# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bist_data_collector.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Varsayılan BIST hisseleri listesi (config dosyası okunamazsa)
DEFAULT_BIST_SYMBOLS = [
    'AKBNK', 'AKSEN', 'ALARK', 'ARCLK', 'ASELS', 'BIMAS', 'DOHOL',
    'EKGYO', 'ENKAI', 'EREGL', 'FROTO', 'GARAN', 'GUBRF', 'HEKTS',
    'ISCTR', 'KCHOL', 'KOZAL', 'KOZAA', 'KRDMD', 'LOGO', 'PETKM',
    'PGSUS', 'SAHOL', 'SASA', 'SISE', 'TAVHL', 'TCELL', 'THYAO',
    'TKFEN', 'TOASO', 'TTKOM', 'TUPRS', 'VAKBN', 'YKBNK'
]


class BISTDataCollector:
    """
    BIST hisse senetleri için kapsamlı veri toplama sistemi.
    """
    
    def __init__(self, symbols: Optional[List[str]] = None):
        """
        Collector'ı başlat
        
        Args:
            symbols: Hisse sembolleri listesi (opsiyonel, yoksa config'den okunur)
        """
        logger.info("="*80)
        logger.info("BIST Veri Toplama Pipeline Başlatılıyor")
        logger.info("="*80)
        
        # Sembolleri belirle: parametre > config > varsayılan
        if symbols:
            self.symbols = symbols
            logger.info("Semboller: Parametre olarak alındı")
        elif get_stock_symbols:
            try:
                self.symbols = get_stock_symbols()
                logger.info("Semboller: config/settings.toml'dan okundu")
            except Exception as e:
                logger.warning(f"Config okunamadı: {e}")
                self.symbols = DEFAULT_BIST_SYMBOLS
                logger.info("Semboller: Varsayılan liste kullanılıyor")
        else:
            self.symbols = DEFAULT_BIST_SYMBOLS
            logger.info("Semboller: Varsayılan liste kullanılıyor")
        
        self.results = []
        
        logger.info(f"Toplam {len(self.symbols)} hisse işlenecek")
        logger.info(f"İlk 10 sembol: {', '.join(self.symbols[:10])}")
        if len(self.symbols) > 10:
            logger.info(f"... ve {len(self.symbols) - 10} sembol daha")
    
    def get_financial_data(self, symbol: str) -> pd.DataFrame:
        """
        Bir hisse için TÜM dönemlerin finansal verilerini getir.
        
        Args:
            symbol: Hisse sembolü
            
        Returns:
            DataFrame: Tüm dönemler için finansal veriler
        """
        try:
            current_year = datetime.now().year
            start_year = 2015  # Daha fazla geçmiş veri için
            
            # Önce financial_group='1' dene (sanayi şirketleri)
            financials = None
            try:
                financials = fetch_financials(
                    symbols=symbol,
                    start_year=start_year,
                    end_year=current_year,
                    exchange='TRY',
                    financial_group='1'
                )
            except Exception as e:
                logger.debug(f"{symbol}: financial_group=1 hatası: {e}")
            
            # Eğer boşsa financial_group='2' dene (bankalar)
            if financials is None or (hasattr(financials, 'empty') and financials.empty):
                try:
                    financials = fetch_financials(
                        symbols=symbol,
                        start_year=start_year,
                        end_year=current_year,
                        exchange='TRY',
                        financial_group='2'
                    )
                except Exception as e:
                    logger.debug(f"{symbol}: financial_group=2 hatası: {e}")
            
            # Hala boşsa boş DataFrame döndür
            if financials is None or (hasattr(financials, 'empty') and financials.empty):
                logger.warning(f"{symbol}: Finansal veri bulunamadı")
                return pd.DataFrame()
            
            logger.debug(f"{symbol}: Finansal veriler alındı - {financials.shape}")
            return financials
            
        except Exception as e:
            logger.warning(f"{symbol}: Finansal veri hatası - {e}")
            return pd.DataFrame()
    
    def get_price_data(self, symbol: str) -> Dict[str, Any]:
        """
        Bir hisse için fiyat verilerini ve getiri hesaplamalarını getir.
        
        Args:
            symbol: Hisse sembolü
            
        Returns:
            Dict: Fiyat getirileri
        """
        try:
            # Son 5 yıllık veri al
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5*365)
            
            # Tarih formatını DD-MM-YYYY'ye çevir
            start_str = start_date.strftime("%d-%m-%Y")
            end_str = end_date.strftime("%d-%m-%Y")
            
            prices = fetch_stock_data(
                symbols=symbol,
                start_date=start_str,
                end_date=end_str
            )
            
            if prices is None or prices.empty:
                logger.warning(f"{symbol}: Fiyat verisi bulunamadı")
                return {
                    'return_1y': None,
                    'return_3y': None,
                    'return_5y': None,
                    'current_price': None
                }
            
            # Tarih sütununu bul ve parse et
            date_col = None
            for col in prices.columns:
                if 'TARIH' in str(col).upper() or 'DATE' in str(col).upper():
                    date_col = col
                    break
            
            if date_col:
                prices[date_col] = pd.to_datetime(prices[date_col], errors='coerce')
                prices = prices.sort_values(by=date_col)
                prices = prices.set_index(date_col)
            
            # Kapanış fiyatı sütununu bul
            close_col = None
            for col in prices.columns:
                col_upper = str(col).upper()
                if 'KAPANIS' in col_upper or 'CLOSE' in col_upper:
                    close_col = col
                    break
            
            if close_col is None:
                logger.warning(f"{symbol}: Kapanış fiyatı sütunu bulunamadı")
                return {
                    'return_1y': None,
                    'return_3y': None,
                    'return_5y': None,
                    'current_price': None
                }
            
            # Güncel fiyat
            current_price = self._safe_numeric(prices[close_col].iloc[-1])
            
            # Getiri hesaplamaları
            return_1y = self._calculate_return(prices, close_col, years=1)
            return_3y = self._calculate_return(prices, close_col, years=3)
            return_5y = self._calculate_return(prices, close_col, years=5)
            
            result = {
                'return_1y': return_1y,
                'return_3y': return_3y,
                'return_5y': return_5y,
                'current_price': current_price
            }
            
            logger.debug(f"{symbol}: Fiyat verileri alındı")
            return result
            
        except Exception as e:
            logger.warning(f"{symbol}: Fiyat verisi hatası - {e}")
            return {
                'return_1y': None,
                'return_3y': None,
                'return_5y': None,
                'current_price': None
            }
    
    def _calculate_return(self, prices: pd.DataFrame, close_col: str, years: int) -> Optional[float]:
        """
        Belirli bir süre için getiri hesapla.
        
        Args:
            prices: Fiyat dataframe'i
            close_col: Kapanış fiyatı sütun adı
            years: Kaç yıl geriye bakılacak
            
        Returns:
            float: Yüzde getiri veya None
        """
        try:
            if len(prices) < 2:
                return None
            
            current_date = prices.index[-1]
            target_date = current_date - pd.DateOffset(years=years)
            
            # Hedef tarihe en yakın veriyi bul
            past_prices = prices[prices.index <= target_date]
            
            if past_prices.empty:
                return None
            
            past_price = self._safe_numeric(past_prices[close_col].iloc[-1])
            current_price = self._safe_numeric(prices[close_col].iloc[-1])
            
            if past_price is None or current_price is None or past_price == 0:
                return None
            
            return_pct = ((current_price - past_price) / past_price) * 100
            return round(return_pct, 2)
            
        except Exception as e:
            logger.debug(f"Getiri hesaplama hatası ({years}y): {e}")
            return None
    
    def _safe_numeric(self, value: Any) -> Optional[float]:
        """
        Bir değeri güvenli şekilde numeric'e çevir.
        
        Args:
            value: Çevrilecek değer
            
        Returns:
            float veya None
        """
        try:
            if value is None or pd.isna(value):
                return None
            
            # String ise temizle
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '').strip()
                if value == '' or value == '-':
                    return None
            
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def collect_stock_data(self, symbol: str) -> Dict[str, Any]:
        """
        Bir hisse için tüm finansal verileri topla ve CSV'ye kaydet.
        
        Args:
            symbol: Hisse sembolü
        """
        logger.info(f"İşleniyor: {symbol}")
        
        try:
            # Finansal verileri al
            financials = self.get_financial_data(symbol)
            
            if financials.empty:
                logger.warning(f"{symbol}: Finansal veri bulunamadı")
                return
            
            # Ticker sütununu kaldır (zaten dosya adında var)
            if 'ticker' in financials.columns:
                financials = financials.drop('ticker', axis=1)
            
            # CSV'ye kaydet
            csv_file = OUTPUT_DIR / f"{symbol}_financials_all_periods.csv"
            financials.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            logger.info(f"✓ {symbol}: {len(financials)} satır kaydedildi -> {csv_file}")
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Genel hata - {e}")
    
    def run(self, output_file: str = None):
        """
        Tüm pipeline'ı çalıştır.
        """
        start_time = time.time()
        
        logger.info(f"Toplam {len(self.symbols)} hisse için veri toplanacak")
        logger.info("="*80)
        
        # Her hisse için veri topla
        for idx, symbol in enumerate(self.symbols, 1):
            logger.info(f"[{idx}/{len(self.symbols)}] {symbol} işleniyor...")
            
            self.collect_stock_data(symbol)
            
            # Her 10 hissede bir ilerleme raporu
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining = (len(self.symbols) - idx) * avg_time
                logger.info(f"İlerleme: {idx}/{len(self.symbols)} - Kalan süre: ~{remaining/60:.1f} dakika")
            
            # Rate limiting - API'yi yormamak için
            time.sleep(2)
        
        elapsed_time = time.time() - start_time
        
        # Özet rapor
        logger.info("="*80)
        logger.info("İŞLEM TAMAMLANDI")
        logger.info("="*80)
        logger.info(f"Toplam hisse: {len(self.symbols)}")
        logger.info(f"Toplam süre: {elapsed_time/60:.2f} dakika")
        logger.info(f"Çıktı klasörü: {OUTPUT_DIR}")
        logger.info("="*80)


def main():
    """Ana fonksiyon"""
    logger.info("BIST Veri Toplama Pipeline başlatılıyor...")
    
    # Collector'ı başlat ve çalıştır
    collector = BISTDataCollector()
    collector.run()
    
    logger.info("\nİşlem tamamlandı!")


if __name__ == "__main__":
    main()
