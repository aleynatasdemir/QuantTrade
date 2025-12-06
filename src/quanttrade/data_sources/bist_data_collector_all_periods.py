"""
BIST Hisse Veri Toplama Pipeline - Tüm Dönemler (INCREMENTAL MOD)
isyatirimhisse kütüphanesi kullanarak BIST'teki her hisse için TÜM dönemlerin finansal verilerini ayrı CSV'lerde toplar.

INCREMENTAL LOGIC:
- Her sembol için mevcut CSV dosyasına bakar
- Son dönem tarihini tespit eder
- Sadece yeni dönemlerin verilerini çeker
- Eski veriyle birleştirir ve duplikatları temizler

Gerekli kurulum:
pip install isyatirimhisse pandas numpy

Kullanım:
python bist_data_collector_all_periods.py
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
        logging.FileHandler('bist_data_collector_all_periods.log', encoding='utf-8'),
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


class BISTDataCollectorAllPeriods:
    """
    BIST hisse senetleri için kapsamlı veri toplama sistemi - INCREMENTAL MOD.
    Her hisse için TÜM dönemlerin finansal verilerini ayrı CSV'lerde kaydeder.
    Mevcut veriler varsa sadece yeni dönemleri çeker.
    """
    
    def __init__(self, symbols: Optional[List[str]] = None):
        """
        Collector'ı başlat
        
        Args:
            symbols: Hisse sembolleri listesi (opsiyonel, yoksa config'den okunur)
        """
        logger.info("="*80)
        logger.info("BIST Veri Toplama Pipeline Başlatılıyor (INCREMENTAL MOD)")
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
        
        # Tarih aralığını config'ten al
        self.start_date = None
        self.end_date = None
        
        if get_stock_date_range:
            try:
                self.start_date, self.end_date = get_stock_date_range()
                logger.info(f"Tarih aralığı: {self.start_date} - {self.end_date}")
            except Exception as e:
                logger.warning(f"Tarih aralığı okunamadı: {e}")
                self.start_date = None
                self.end_date = None
        
        logger.info(f"Toplam {len(self.symbols)} hisse işlenecek")
        logger.info(f"İlk 10 sembol: {', '.join(self.symbols[:10])}")
        if len(self.symbols) > 10:
            logger.info(f"... ve {len(self.symbols) - 10} sembol daha")
        
        # İstatistikler
        self.skip_count = 0
        self.update_count = 0
        self.fail_count = 0
    
    def get_existing_periods(self, file_path: Path) -> tuple:
        """
        Mevcut CSV dosyasındaki dönemleri ve son dönemi tespit eder.
        
        Args:
            file_path: CSV dosya yolu
            
        Returns:
            tuple: (existing_periods set, last_period str, existing_df)
        """
        if not file_path.exists():
            return set(), None, None
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            if df.empty or 'period' not in df.columns:
                return set(), None, None
            
            existing_periods = set(df['period'].unique())
            
            # Son dönemi bul (örn: 2024/12)
            sorted_periods = sorted(
                [p for p in existing_periods if isinstance(p, str) and '/' in p],
                key=lambda x: tuple(map(int, x.split('/')))
            )
            
            last_period = sorted_periods[-1] if sorted_periods else None
            
            return existing_periods, last_period, df
            
        except Exception as e:
            logger.warning(f"Dosya okuma hatası: {e}")
            return set(), None, None
    
    def period_to_year(self, period_str: str) -> Optional[int]:
        """Dönem string'inden yıl çıkar (örn: '2024/12' -> 2024)"""
        try:
            if '/' in str(period_str):
                return int(str(period_str).split('/')[0])
        except:
            pass
        return None
    
    def period_to_date(self, period_str: str) -> Optional[datetime]:
        """Dönem string'ini datetime'a çevirir (örn: '2024/12' -> 2024-12-31)"""
        try:
            if '/' in str(period_str):
                year, month = period_str.split('/')
                year = int(year)
                month = int(month)
                # Ayın son gününü hesapla
                if month == 12:
                    return datetime(year, 12, 31)
                else:
                    from calendar import monthrange
                    _, last_day = monthrange(year, month)
                    return datetime(year, month, last_day)
        except:
            pass
        return None
    
    def get_last_business_day(self, date: datetime = None) -> datetime:
        """En son iş gününü döndürür. Haftasonu ise Cuma'ya geri gider."""
        if date is None:
            date = datetime.now()
        date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        while date.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
            date -= timedelta(days=1)
        return date
    
    def is_up_to_date(self, last_period: str, end_date: str) -> bool:
        """
        Verinin güncel olup olmadığını kontrol eder.
        Tam tarih karşılaştırması yapar ve haftasonlarını dikkate alır.
        
        Args:
            last_period: Son dönem (örn: '2024/12')
            end_date: Config'teki bitiş tarihi (YYYY-MM-DD)
            
        Returns:
            bool: Veri güncel mi?
        """
        if not last_period or not end_date:
            return False
        
        try:
            # Son dönemi datetime'a çevir
            last_date = self.period_to_date(last_period)
            if last_date is None:
                return False
            
            # Hedef tarihi parse et ve son iş gününe ayarla
            target_date = datetime.strptime(end_date, "%Y-%m-%d")
            target_date = self.get_last_business_day(target_date)
            
            # Tam tarih karşılaştırması
            return last_date >= target_date
        except:
            return False
    
    def get_financial_data_all_periods(self, symbol: str, start_year: int = None) -> pd.DataFrame:
        """
        Bir hisse için TÜM dönemlerin finansal verilerini getir (INCREMENTAL).
        
        Args:
            symbol: Hisse sembolü
            start_year: Başlangıç yılı (incremental mod için)
            
        Returns:
            DataFrame: Tüm dönemler için finansal veriler (her satır bir dönem)
        """
        try:
            current_year = datetime.now().year
            if start_year is None:
                start_year = 2015  # Varsayılan başlangıç yılı
            
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
            
            # Format: Satırlar = kalemler, Sütunlar = dönemler (2020/3, 2020/6, ...)
            # FINANCIAL_ITEM_NAME_TR sütununda Türkçe kalem adları var
            
            # Dönem sütunlarını bul (2020/3, 2020/6 formatında)
            period_cols = [c for c in financials.columns if isinstance(c, str) and '/' in c]
            
            if not period_cols:
                logger.warning(f"{symbol}: Dönem sütunları bulunamadı")
                return pd.DataFrame()
            
            # Dönemleri sırala
            period_cols = sorted(period_cols, key=lambda x: tuple(map(int, x.split('/'))))
            
            logger.info(f"{symbol}: {len(period_cols)} dönem bulundu ({period_cols[0]} - {period_cols[-1]})")
            
            # FINANCIAL_ITEM_NAME_TR veya FINANCIAL_ITEM_NAME_EN sütununu bul
            item_name_col = None
            for col in ['FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN']:
                if col in financials.columns:
                    item_name_col = col
                    break
            
            if item_name_col is None:
                logger.warning(f"{symbol}: Kalem adı sütunu bulunamadı")
                return pd.DataFrame()
            
            # DataFrame'i set_index yap
            df = financials.set_index(item_name_col)
            
            # Her dönem için veri topla
            all_periods_data = []
            
            for period in period_cols:
                period_data = {
                    'ticker': symbol,
                    'period': period,
                    'net_profit': None,
                    'sales': None,
                    'total_debt': None,
                    'total_equity': None,
                }
                
                # Kalem arama fonksiyonu - bu dönem için
                def find_item_value(aliases: List[str]) -> Optional[float]:
                    """Verilen aliaslardan birini içeren satırı bul ve değeri döndür"""
                    for alias in aliases:
                        for idx in df.index:
                            if pd.notna(idx) and alias.upper() in str(idx).upper():
                                try:
                                    val = df.loc[idx, period]
                                    numeric_val = self._safe_numeric(val)
                                    if numeric_val is not None:
                                        return numeric_val
                                except Exception:
                                    continue
                    return None
                
                # Net Kar (Net Dönem Karı/Zararı)
                period_data['net_profit'] = find_item_value([
                    'NET DÖNEM KARI',
                    'NET DÖNEM ZARARI', 
                    'NET KAR',
                    'DÖNEM KARI',
                    'DÖNEM NET KARI'
                ])
                
                # Satışlar (Net Satışlar, Hasılat) - Bankalar için Faiz Geliri de ekle
                period_data['sales'] = find_item_value([
                    'NET SATIŞLAR',
                    'SATIŞLAR',
                    'HASILAT',
                    'BRÜT SATIŞLAR',
                    'NET FAİZ GELİRİ',  # Bankalar için
                    'FAİZ GELİRİ',
                    'TOPLAM GELİRLER',
                    'TOPLAM FAİZ GELİRİ'
                ])
                
                # Toplam Borç (Kısa + Uzun Vadeli Borçlanmalar)
                period_data['total_debt'] = find_item_value([
                    'TOPLAM BORÇLAR',
                    'FINANSAL BORÇLAR',
                    'TOPLAM YÜKÜMLÜLÜKLER',
                    'KISA VADELİ BORÇLAR',
                    'UZUN VADELİ BORÇLAR',
                    'BORÇLAR TOPLAMI'
                ])
                
                # Özkaynak
                period_data['total_equity'] = find_item_value([
                    'ÖZKAYNAKLAR',
                    'ANA ORTAKLIK PAYINA AİT ÖZKAYNAKLAR',
                    'ÖZKAYNAK TOPLAMI',
                    'TOPLAM ÖZKAYNAKLAR'
                ])
                
                all_periods_data.append(period_data)
            
            result_df = pd.DataFrame(all_periods_data)
            logger.info(f"✓ {symbol}: {len(result_df)} dönem bulundu")
            
            # Tarih aralığına göre filtrele
            if self.start_date and self.end_date:
                result_df = self._filter_by_date_range(result_df, self.start_date, self.end_date)
                logger.info(f"  → Filtrelendikten sonra: {len(result_df)} dönem ({self.start_date} - {self.end_date})")
            
            return result_df
            
        except Exception as e:
            logger.error(f"{symbol}: Finansal veri hatası - {e}")
            return pd.DataFrame()
    
    def _filter_by_date_range(self, df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """
        DataFrame'i tarih aralığına göre filtrele.
        
        Args:
            df: Filtrelenecek DataFrame (period sütunu olmalı)
            start_date: Başlangıç tarihi (YYYY-MM-DD formatında)
            end_date: Bitiş tarihi (YYYY-MM-DD formatında)
            
        Returns:
            Filtrelenmiş DataFrame
        """
        try:
            if df.empty or 'period' not in df.columns:
                return df
            
            # Dönem sütununu datetime'a çevir (2024/12 -> 2024-12-31)
            def period_to_date(period_str):
                try:
                    year, quarter = period_str.split('/')
                    year = int(year)
                    quarter = int(quarter)
                    # Ayın son gününü al
                    month = quarter * 3
                    if month > 12:
                        month = 12
                    # Ayın son gütünü bul
                    if month == 12:
                        next_month_date = datetime(year + 1, 1, 1)
                    else:
                        next_month_date = datetime(year, month + 1, 1)
                    last_day = (next_month_date - timedelta(days=1)).day
                    return datetime(year, month, min(last_day, 31))
                except:
                    return None
            
            # Dönemleri datetime'a çevir
            df['period_date'] = df['period'].apply(period_to_date)
            
            # Tarih aralığını parse et
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # Filtrele
            mask = (df['period_date'] >= start_dt) & (df['period_date'] <= end_dt)
            filtered_df = df[mask].copy()
            
            # Geçici sütunu sil
            filtered_df = filtered_df.drop('period_date', axis=1)
            
            return filtered_df
        except Exception as e:
            logger.warning(f"Tarih filtreleme hatası: {e}")
            return df
    
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
    
    def merge_financial_data(self, old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """
        Eski ve yeni finansal verileri birleştirir.
        
        Args:
            old_df: Mevcut veri
            new_df: Yeni çekilen veri
            
        Returns:
            DataFrame: Birleştirilmiş veri
        """
        if old_df is None or old_df.empty:
            return new_df
        if new_df is None or new_df.empty:
            return old_df
        
        # Birleştir
        combined = pd.concat([old_df, new_df], ignore_index=True)
        
        # Duplikatları temizle (period sütununa göre)
        if 'period' in combined.columns:
            combined = combined.drop_duplicates(subset=['period'], keep='last')
            
            # Dönemleri sırala
            try:
                combined['_sort_key'] = combined['period'].apply(
                    lambda x: tuple(map(int, str(x).split('/'))) if '/' in str(x) else (0, 0)
                )
                combined = combined.sort_values('_sort_key')
                combined = combined.drop('_sort_key', axis=1)
            except:
                pass
        
        return combined.reset_index(drop=True)
    
    def collect_stock_data(self, symbol: str, output_dir: str) -> tuple:
        """
        Bir hisse için tüm dönemlerin verilerini topla ve ayrı CSV'ye kaydet (INCREMENTAL).
        
        Args:
            symbol: Hisse sembolü
            output_dir: Çıktı dizini
            
        Returns:
            tuple: (status, periods_count) - status: 'skip', 'update', 'new', 'fail'
        """
        output_file = Path(output_dir) / f"{symbol}_financials_all_periods.csv"
        
        # Mevcut veriyi kontrol et
        existing_periods, last_period, old_df = self.get_existing_periods(output_file)
        
        # Güncellik kontrolü
        if last_period and self.is_up_to_date(last_period, self.end_date):
            logger.info(f"✓ {symbol}: Güncel (son dönem: {last_period})")
            return ('skip', len(existing_periods) if existing_periods else 0)
        
        try:
            # Incremental mod: son dönemin yılından itibaren çek
            start_year = None
            if last_period:
                start_year = self.period_to_year(last_period)
                if start_year:
                    start_year = start_year - 1  # Güvenlik için 1 yıl geriye git
                logger.info(f"  → Incremental mod: {start_year} yılından itibaren")
            
            # Finansal verileri al
            financial_df = self.get_financial_data_all_periods(symbol, start_year)
            
            if financial_df.empty and (old_df is None or old_df.empty):
                logger.warning(f"✗ {symbol}: Finansal veri bulunamadı")
                return ('fail', 0)
            
            # Rate limiting
            time.sleep(1)
            
            # Fiyat verilerini al
            price_data = self.get_price_data(symbol)
            
            # Yeni verileri birleştir
            if not financial_df.empty:
                for col, val in price_data.items():
                    financial_df[col] = val
                
                combined = self.merge_financial_data(old_df, financial_df)
            else:
                combined = old_df
            
            # Kaydet
            combined.to_csv(output_file, index=False, encoding='utf-8')
            
            new_periods = len(combined) - (len(old_df) if old_df is not None else 0)
            if last_period:
                logger.info(f"✓ {symbol}: +{new_periods} yeni dönem ({len(combined)} toplam)")
                return ('update', len(combined))
            else:
                logger.info(f"✓ {symbol}: {len(combined)} dönem kaydedildi")
                return ('new', len(combined))
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Genel hata - {e}")
            return ('fail', 0)
    
    def run(self):
        """
        Tüm pipeline'ı çalıştır (INCREMENTAL MOD).
        """
        start_time = time.time()
        
        # Çıktı dizini
        output_dir = str(OUTPUT_DIR)
        
        logger.info(f"\nToplam {len(self.symbols)} hisse için veri toplanacak")
        logger.info(f"Tarih aralığı: {self.start_date} - {self.end_date}")
        logger.info(f"Çıktı dizini: {output_dir}")
        logger.info("\nNOT: Mevcut veriler kontrol edilecek, sadece yeni dönemler çekilecek.")
        logger.info("="*80)
        
        # İstatistikler
        total_stocks = len(self.symbols)
        skip_count = 0
        update_count = 0
        new_count = 0
        fail_count = 0
        total_periods = 0
        
        # Her hisse için veri topla
        for idx, symbol in enumerate(self.symbols, 1):
            logger.info(f"\n[{idx}/{total_stocks}] {symbol}...")
            
            status, periods = self.collect_stock_data(symbol, output_dir)
            
            if status == 'skip':
                skip_count += 1
            elif status == 'update':
                update_count += 1
            elif status == 'new':
                new_count += 1
            else:
                fail_count += 1
            
            total_periods += periods
            
            # Her 10 hissede bir ilerleme raporu
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining = (total_stocks - idx) * avg_time
                logger.info(f"\n📊 İlerleme: {idx}/{total_stocks} - Kalan süre: ~{remaining/60:.1f} dakika")
                logger.info(f"   Atlanan: {skip_count}, Güncellenen: {update_count}, Yeni: {new_count}")
            
            # Rate limiting - API'yi yormamak için
            time.sleep(2)
        
        elapsed_time = time.time() - start_time
        
        # Özet rapor
        logger.info("\n" + "="*80)
        logger.info("İŞLEM TAMAMLANDI (INCREMENTAL MOD)")
        logger.info("="*80)
        logger.info(f"Toplam hisse: {total_stocks}")
        logger.info(f"Atlanan (güncel): {skip_count}")
        logger.info(f"Güncellenen: {update_count}")
        logger.info(f"Yeni eklenen: {new_count}")
        logger.info(f"Başarısız: {fail_count}")
        logger.info(f"Toplam dönem sayısı: {total_periods}")
        logger.info(f"Tarih aralığı: {self.start_date} - {self.end_date}")
        logger.info(f"Toplam süre: {elapsed_time/60:.2f} dakika")
        logger.info(f"Çıktı dizini: {output_dir}")
        logger.info("="*80)
        
        # Oluşturulan dosyaları listele
        logger.info("\n📁 Dosyalar:")
        csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
        logger.info(f"Toplam {len(csv_files)} CSV dosyası")


def main():
    """Ana fonksiyon"""
    logger.info("BIST Veri Toplama Pipeline başlatılıyor (INCREMENTAL MOD)...")
    
    # Collector'ı başlat ve çalıştır
    collector = BISTDataCollectorAllPeriods()
    collector.run()
    
    logger.info("\n🎉 İşlem tamamlandı!")


if __name__ == "__main__":
    main()
