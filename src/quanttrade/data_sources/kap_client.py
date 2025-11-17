"""
KAP Client - pykap kütüphanesi için wrapper sınıfı

Bu modül, Kamuyu Aydınlatma Platformu (KAP) verilerini pykap kullanarak
çekmek için yüksek seviye API sağlar.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Union
from datetime import datetime, timedelta
import logging
import time
import toml
from pathlib import Path

try:
    from pykap import KAPClient
    from pykap.company import BISTCompany
except ImportError:
    KAPClient = None
    BISTCompany = None

from quanttrade.config import CONFIG_DIR, ROOT_DIR


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KAP data dizini
KAP_DATA_DIR = ROOT_DIR / "data" / "raw" / "kap"
KAP_DATA_DIR.mkdir(parents=True, exist_ok=True)


class KapDataClient:
    """
    KAP (Kamuyu Aydınlatma Platformu) verilerini çekmek için client sınıfı.
    
    Bu sınıf pykap kütüphanesini kullanarak:
    - Finansal rapor duyurularını
    - Temettü duyurularını
    - Hisse bölünmesi duyurularını
    çeker ve işler.
    
    Attributes:
        settings (dict): kap_settings.toml'dan yüklenen ayarlar
        client: pykap KAPClient nesnesi (eğer pykap yüklüyse)
    """
    
    def __init__(self):
        """
        KapDataClient'ı başlatır ve ayarları yükler.
        
        Raises:
            ImportError: pykap paketi kurulu değilse
            FileNotFoundError: kap_settings.toml bulunamazsa
        """
        if KAPClient is None:
            raise ImportError(
                "pykap paketi kurulu değil. Lütfen 'pip install pykap' komutunu çalıştırın."
            )
        
        # Ayarları yükle
        self.settings = self._load_settings()
        
        # KAP client'ı başlat
        # Not: pykap kullanımına göre client başlatılır
        # Bazı versiyonlarda API key gerekebilir
        try:
            self.client = KAPClient()
            logger.info("KAP Client başarıyla oluşturuldu")
        except Exception as e:
            logger.warning(f"KAP Client oluşturulurken uyarı: {e}")
            self.client = None
        
        # Dizinleri hazırla
        KAP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_settings(self) -> Dict:
        """
        kap_settings.toml dosyasını yükler.
        
        Returns:
            Dict: KAP ayarları
            
        Raises:
            FileNotFoundError: Ayar dosyası bulunamazsa
        """
        settings_path = CONFIG_DIR / "kap_settings.toml"
        
        if not settings_path.exists():
            raise FileNotFoundError(
                f"KAP ayar dosyası bulunamadı: {settings_path}\n"
                "Lütfen config/kap_settings.toml dosyasının mevcut olduğundan emin olun."
            )
        
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = toml.load(f)
        
        logger.info(f"KAP ayarları yüklendi: {len(settings.get('kap', {}).get('tickers', []))} ticker")
        return settings
    
    def _parse_date(self, date_str: Union[str, datetime, pd.Timestamp, None]) -> Optional[str]:
        """
        Tarih string'ini YYYY-MM-DD formatına dönüştürür.
        
        Args:
            date_str: Tarih (string, datetime, Timestamp veya None)
            
        Returns:
            str: YYYY-MM-DD formatında tarih string'i veya None
        """
        if date_str is None:
            return None
        
        if isinstance(date_str, str):
            try:
                dt = pd.to_datetime(date_str)
                return dt.strftime("%Y-%m-%d")
            except:
                return None
        elif isinstance(date_str, (datetime, pd.Timestamp)):
            return date_str.strftime("%Y-%m-%d")
        
        return None
    
    def get_financial_disclosures_for_ticker(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Belirli bir hisse için finansal rapor duyurularını çeker.
        
        Args:
            ticker: Hisse senedi kodu (örn: "BIMAS")
            start_date: Başlangıç tarihi (YYYY-MM-DD). None ise settings'ten alınır.
            end_date: Bitiş tarihi (YYYY-MM-DD). None ise settings'ten alınır.
        
        Returns:
            pd.DataFrame: Finansal rapor duyuruları
                Kolonlar: ticker, period_end_date, announcement_date, 
                         report_type, currency, raw_title
        """
        # Tarih aralığını belirle
        if start_date is None:
            start_date = self.settings.get("kap", {}).get("start_date", "2015-01-01")
        if end_date is None:
            end_date = self.settings.get("kap", {}).get("end_date", "2025-01-01")
        
        logger.info(f"Finansal raporlar çekiliyor: {ticker} ({start_date} - {end_date})")
        
        try:
            # pykap ile şirket nesnesi oluştur
            # Not: Gerçek pykap API kullanımı:
            # company = BISTCompany(ticker)
            # disclosures = company.get_disclosures(
            #     start_date=start_date,
            #     end_date=end_date,
            #     disclosure_type="financial_statement"  # veya uygun tip
            # )
            
            # Placeholder: pykap API'sine göre özelleştirilmeli
            disclosures = self._fetch_disclosures_from_pykap(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                disclosure_category="financial"
            )
            
            if disclosures is None or len(disclosures) == 0:
                logger.warning(f"Finansal rapor bulunamadı: {ticker}")
                return pd.DataFrame()
            
            # DataFrame'e dönüştür
            df = pd.DataFrame(disclosures)
            
            # Standart kolonları oluştur
            df['ticker'] = ticker
            
            # Tarih kolonlarını düzenle
            if 'disclosureDate' in df.columns:
                df['announcement_date'] = pd.to_datetime(df['disclosureDate']).dt.strftime("%Y-%m-%d")
            elif 'date' in df.columns:
                df['announcement_date'] = pd.to_datetime(df['date']).dt.strftime("%Y-%m-%d")
            
            # Dönem sonu tarihini çıkar (genellikle başlıkta veya detayda olur)
            df['period_end_date'] = self._extract_period_end_date(df)
            
            # Diğer alanlar
            df['report_type'] = df.get('reportType', 'unknown')
            df['currency'] = df.get('currency', 'TRY')
            df['raw_title'] = df.get('subject', '') + ' - ' + df.get('summary', '')
            
            # Sadece gerekli kolonları seç
            result_columns = [
                'ticker', 'period_end_date', 'announcement_date', 
                'report_type', 'currency', 'raw_title'
            ]
            
            # Mevcut kolonları filtrele
            available_columns = [col for col in result_columns if col in df.columns]
            df = df[available_columns]
            
            logger.info(f"✓ {len(df)} finansal rapor kaydı bulundu: {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Finansal rapor çekilirken hata ({ticker}): {e}")
            return pd.DataFrame()
    
    def get_dividend_disclosures_for_ticker(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Belirli bir hisse için temettü duyurularını çeker.
        
        Args:
            ticker: Hisse senedi kodu (örn: "BIMAS")
            start_date: Başlangıç tarihi (YYYY-MM-DD)
            end_date: Bitiş tarihi (YYYY-MM-DD)
        
        Returns:
            pd.DataFrame: Temettü duyuruları
                Kolonlar: ticker, announcement_date, gross_dividend_per_share,
                         net_dividend_per_share, payment_date, raw_title
        """
        if start_date is None:
            start_date = self.settings.get("kap", {}).get("start_date", "2015-01-01")
        if end_date is None:
            end_date = self.settings.get("kap", {}).get("end_date", "2025-01-01")
        
        logger.info(f"Temettü duyuruları çekiliyor: {ticker} ({start_date} - {end_date})")
        
        try:
            # pykap ile temettü duyurularını çek
            # Placeholder: gerçek pykap API kullanımı
            disclosures = self._fetch_disclosures_from_pykap(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                disclosure_category="dividend"
            )
            
            if disclosures is None or len(disclosures) == 0:
                logger.warning(f"Temettü duyurusu bulunamadı: {ticker}")
                return pd.DataFrame()
            
            df = pd.DataFrame(disclosures)
            df['ticker'] = ticker
            
            # Tarih alanları
            if 'disclosureDate' in df.columns:
                df['announcement_date'] = pd.to_datetime(df['disclosureDate']).dt.strftime("%Y-%m-%d")
            
            # Temettü tutarları (pykap'tan gelen alanlara göre)
            df['gross_dividend_per_share'] = df.get('grossDividend', np.nan)
            df['net_dividend_per_share'] = df.get('netDividend', np.nan)
            df['payment_date'] = self._parse_date(df.get('paymentDate'))
            df['raw_title'] = df.get('subject', '')
            
            result_columns = [
                'ticker', 'announcement_date', 'gross_dividend_per_share',
                'net_dividend_per_share', 'payment_date', 'raw_title'
            ]
            
            available_columns = [col for col in result_columns if col in df.columns]
            df = df[available_columns]
            
            logger.info(f"✓ {len(df)} temettü duyurusu bulundu: {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Temettü verileri çekilirken hata ({ticker}): {e}")
            return pd.DataFrame()
    
    def get_split_disclosures_for_ticker(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Belirli bir hisse için bölünme duyurularını çeker.
        
        Args:
            ticker: Hisse senedi kodu (örn: "BIMAS")
            start_date: Başlangıç tarihi (YYYY-MM-DD)
            end_date: Bitiş tarihi (YYYY-MM-DD)
        
        Returns:
            pd.DataFrame: Bölünme duyuruları
                Kolonlar: ticker, announcement_date, split_ratio, 
                         effective_date, raw_title
        """
        if start_date is None:
            start_date = self.settings.get("kap", {}).get("start_date", "2015-01-01")
        if end_date is None:
            end_date = self.settings.get("kap", {}).get("end_date", "2025-01-01")
        
        logger.info(f"Bölünme duyuruları çekiliyor: {ticker} ({start_date} - {end_date})")
        
        try:
            # pykap ile bölünme duyurularını çek
            disclosures = self._fetch_disclosures_from_pykap(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                disclosure_category="split"
            )
            
            if disclosures is None or len(disclosures) == 0:
                logger.warning(f"Bölünme duyurusu bulunamadı: {ticker}")
                return pd.DataFrame()
            
            df = pd.DataFrame(disclosures)
            df['ticker'] = ticker
            
            # Tarih alanları
            if 'disclosureDate' in df.columns:
                df['announcement_date'] = pd.to_datetime(df['disclosureDate']).dt.strftime("%Y-%m-%d")
            
            # Bölünme oranı (örn: 1:2 bölünme için 2.0)
            df['split_ratio'] = df.get('splitRatio', np.nan)
            df['effective_date'] = self._parse_date(df.get('effectiveDate'))
            df['raw_title'] = df.get('subject', '')
            
            result_columns = [
                'ticker', 'announcement_date', 'split_ratio', 
                'effective_date', 'raw_title'
            ]
            
            available_columns = [col for col in result_columns if col in df.columns]
            df = df[available_columns]
            
            logger.info(f"✓ {len(df)} bölünme duyurusu bulundu: {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Bölünme verileri çekilirken hata ({ticker}): {e}")
            return pd.DataFrame()
    
    def _fetch_disclosures_from_pykap(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        disclosure_category: str
    ) -> List[Dict]:
        """
        pykap kullanarak duyuruları çeker.
        
        Bu fonksiyon gerçek pykap API kullanımına göre özelleştirilmelidir.
        
        Args:
            ticker: Hisse kodu
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi
            disclosure_category: "financial", "dividend", "split"
        
        Returns:
            List[Dict]: Duyuru listesi
        """
        # NOT: Bu fonksiyon pykap'ın gerçek API'sine göre güncellenmelidir
        # Aşağıda örnek bir kullanım şablonu:
        
        try:
            # Rate limiting
            rate_limit = self.settings.get("kap", {}).get("options", {}).get("rate_limit_delay", 1.0)
            time.sleep(rate_limit)
            
            # pykap kullanarak veri çek
            # Örnek: 
            # company = BISTCompany(ticker)
            # disclosures = company.get_disclosures(
            #     start_date=start_date,
            #     end_date=end_date,
            #     subject_filter=self._get_subject_filter(disclosure_category)
            # )
            # return disclosures
            
            # Placeholder implementation
            logger.warning(
                f"pykap API çağrısı placeholder modda çalışıyor. "
                f"Gerçek implementasyon için _fetch_disclosures_from_pykap fonksiyonunu "
                f"pykap dokümantasyonuna göre güncelleyin."
            )
            
            # Boş liste döndür (gerçek implementasyonda pykap'tan gelen veri dönecek)
            return []
            
        except Exception as e:
            logger.error(f"pykap veri çekme hatası: {e}")
            return []
    
    def _get_subject_filter(self, disclosure_category: str) -> Optional[str]:
        """
        Duyuru kategorisine göre KAP konu filtresi döndürür.
        
        Args:
            disclosure_category: "financial", "dividend", "split"
        
        Returns:
            str: KAP subject filter
        """
        category_map = {
            "financial": "Finansal Tablolar",
            "dividend": "Kar Payı",
            "split": "Sermaye Artırımı"
        }
        return category_map.get(disclosure_category)
    
    def _extract_period_end_date(self, df: pd.DataFrame) -> pd.Series:
        """
        Finansal rapor başlığından dönem sonu tarihini çıkarır.
        
        Args:
            df: Duyuru DataFrame'i
        
        Returns:
            pd.Series: Dönem sonu tarihleri
        """
        # Başlıktan veya özel alandan dönem bilgisini çıkar
        # Örnek: "31.03.2024 Dönemine Ait Finansal Tablolar"
        # TODO: Gerçek veri formatına göre özelleştir
        return pd.Series([None] * len(df))
    
    def fetch_all_financials_for_all_tickers(self) -> pd.DataFrame:
        """
        Ayarlarda tanımlı tüm ticker'lar için finansal rapor verilerini çeker.
        
        Returns:
            pd.DataFrame: Tüm ticker'ların finansal rapor verileri
        """
        tickers = self.settings.get("kap", {}).get("tickers", [])
        start_date = self.settings.get("kap", {}).get("start_date")
        end_date = self.settings.get("kap", {}).get("end_date")
        
        logger.info(f"Toplam {len(tickers)} ticker için finansal veriler çekiliyor...")
        
        all_data = []
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{len(tickers)}] İşleniyor: {ticker}")
            df = self.get_financial_disclosures_for_ticker(ticker, start_date, end_date)
            
            if not df.empty:
                all_data.append(df)
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"✓ Toplam {len(result)} finansal rapor kaydı toplandı")
            return result
        else:
            logger.warning("Hiç finansal rapor verisi çekilemedi")
            return pd.DataFrame()
    
    def fetch_all_corporate_actions_for_all_tickers(self) -> pd.DataFrame:
        """
        Ayarlarda tanımlı tüm ticker'lar için corporate actions verilerini çeker.
        
        Returns:
            pd.DataFrame: Tüm ticker'ların temettü ve bölünme verileri
        """
        tickers = self.settings.get("kap", {}).get("tickers", [])
        start_date = self.settings.get("kap", {}).get("start_date")
        end_date = self.settings.get("kap", {}).get("end_date")
        
        logger.info(f"Toplam {len(tickers)} ticker için corporate actions çekiliyor...")
        
        all_data = []
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{len(tickers)}] İşleniyor: {ticker}")
            
            # Temettü verileri
            df_div = self.get_dividend_disclosures_for_ticker(ticker, start_date, end_date)
            if not df_div.empty:
                df_div['action_type'] = 'dividend'
                all_data.append(df_div)
            
            # Bölünme verileri
            df_split = self.get_split_disclosures_for_ticker(ticker, start_date, end_date)
            if not df_split.empty:
                df_split['action_type'] = 'split'
                all_data.append(df_split)
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            
            # Kolonları yeniden düzenle
            base_columns = ['ticker', 'action_type', 'announcement_date']
            other_columns = [col for col in result.columns if col not in base_columns]
            result = result[base_columns + other_columns]
            
            logger.info(f"✓ Toplam {len(result)} corporate action kaydı toplandı")
            return result
        else:
            logger.warning("Hiç corporate action verisi çekilemedi")
            return pd.DataFrame()
    
    def save_financials_csv(self, df: pd.DataFrame, filename: str = "financials.csv") -> str:
        """
        Finansal rapor DataFrame'ini CSV olarak kaydeder.
        
        Args:
            df: Finansal rapor verileri
            filename: Çıktı dosya adı
        
        Returns:
            str: Kaydedilen dosyanın yolu
        """
        output_path = KAP_DATA_DIR / filename
        df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info(f"✓ Finansal veriler kaydedildi: {output_path}")
        logger.info(f"  Toplam {len(df)} satır, {len(df.columns)} kolon")
        return str(output_path)
    
    def save_corporate_actions_csv(
        self, 
        df: pd.DataFrame, 
        filename: str = "corporate_actions.csv"
    ) -> str:
        """
        Corporate actions DataFrame'ini CSV olarak kaydeder.
        
        Args:
            df: Corporate actions verileri
            filename: Çıktı dosya adı
        
        Returns:
            str: Kaydedilen dosyanın yolu
        """
        output_path = KAP_DATA_DIR / filename
        df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info(f"✓ Corporate actions verileri kaydedildi: {output_path}")
        logger.info(f"  Toplam {len(df)} satır, {len(df.columns)} kolon")
        return str(output_path)
