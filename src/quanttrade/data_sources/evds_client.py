"""
EVDS Client - TCMB EVDS API ile veri çekme işlemlerini yönetir
"""

import pandas as pd
from typing import List, Dict, Optional, Union
from datetime import datetime
import logging

try:
    from evdspy import evdspyAPI
except ImportError:
    # evdspy kurulu değilse, kullanıcıya bilgi ver
    evdspyAPI = None

from quanttrade.config import (
    get_evds_api_key, 
    get_evds_settings, 
    MACRO_DATA_DIR
)


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EVDSClient:
    """
    TCMB EVDS API ile etkileşim için client sınıfı.
    
    Bu sınıf EVDS API'den makroekonomik veri çekme, işleme ve 
    kaydetme işlemlerini gerçekleştirir.
    
    Attributes:
        api_key (str): EVDS API anahtarı
        client: evdspy API client nesnesi
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        EVDSClient'ı başlatır.
        
        Args:
            api_key (str, optional): EVDS API anahtarı. 
                                     Verilmezse .env'den okunur.
                                     
        Raises:
            ImportError: evdspy paketi kurulu değilse
            ValueError: API anahtarı geçersizse
        """
        if evdspyAPI is None:
            raise ImportError(
                "evdspy paketi kurulu değil. Lütfen 'pip install evdspy' komutunu çalıştırın."
            )
        
        self.api_key = api_key or get_evds_api_key()
        
        try:
            # evdspy API client'ını oluştur
            # Not: evdspy v2.0+ için API imzası: evdspyAPI(api_key)
            self.client = evdspyAPI(self.api_key)
            logger.info("EVDS Client başarıyla oluşturuldu")
        except Exception as e:
            logger.error(f"EVDS Client oluşturulurken hata: {e}")
            raise
    
    def fetch_series(
        self, 
        series_codes: Union[str, List[str]], 
        start_date: str,
        end_date: str,
        frequency: str = "daily"
    ) -> pd.DataFrame:
        """
        EVDS'ten belirtilen serileri çeker.
        
        Args:
            series_codes (str or List[str]): EVDS seri kodu veya kodları listesi
            start_date (str): Başlangıç tarihi (YYYY-MM-DD formatında)
            end_date (str): Bitiş tarihi (YYYY-MM-DD formatında)
            frequency (str): Veri frekansı. Varsayılan: "daily"
                           Seçenekler: "daily", "weekly", "monthly", "quarterly", "yearly"
        
        Returns:
            pd.DataFrame: Tarih index'li DataFrame. Kolonlar seri kodlarıdır.
        
        Raises:
            ValueError: Geçersiz tarih formatı veya seri kodu
        """
        # Tek bir string ise liste haline getir
        if isinstance(series_codes, str):
            series_codes = [series_codes]
        
        # Boş liste kontrolü
        if not series_codes or all(not code for code in series_codes):
            logger.warning("Çekilecek seri kodu bulunamadı")
            return pd.DataFrame()
        
        # Boş seri kodlarını filtrele
        series_codes = [code for code in series_codes if code]
        
        # Tarih formatını EVDS API için dönüştür (DD-MM-YYYY)
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            evds_start = start_dt.strftime("%d-%m-%Y")
            evds_end = end_dt.strftime("%d-%m-%Y")
        except ValueError as e:
            raise ValueError(
                f"Geçersiz tarih formatı. YYYY-MM-DD formatında olmalı. Hata: {e}"
            )
        
        logger.info(
            f"EVDS'ten {len(series_codes)} seri çekiliyor: "
            f"{', '.join(series_codes)} ({start_date} - {end_date})"
        )
        
        try:
            # EVDS API'den veri çek
            # evdspy API imzası: get_data(series, startdate, enddate, frequency)
            # Series kodları virgülle ayrılmış string olarak gönderilir
            series_string = ",".join(series_codes)
            
            df = self.client.get_data(
                series=series_string,
                startdate=evds_start,
                enddate=evds_end,
                frequency=frequency
            )
            
            if df is None or df.empty:
                logger.warning("EVDS'ten veri çekilemedi veya sonuç boş")
                return pd.DataFrame()
            
            # Tarih sütununu düzenle
            # evdspy genellikle 'Tarih' veya 'YEARWEEK' gibi bir sütun döndürür
            date_col = None
            for col in ['Tarih', 'DATE', 'YEARWEEK']:
                if col in df.columns:
                    date_col = col
                    break
            
            if date_col:
                # Tarih sütununu 'date' olarak yeniden adlandır ve index yap
                df = df.rename(columns={date_col: 'date'})
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                df = df.sort_index()
            
            logger.info(f"Başarıyla {len(df)} satır veri çekildi")
            return df
            
        except Exception as e:
            logger.error(f"EVDS'ten veri çekilirken hata: {e}")
            raise
    
    def fetch_and_save_default_macro(
        self,
        output_filename: str = "evds_macro_daily.csv"
    ) -> str:
        """
        settings.toml'da tanımlanan varsayılan makro serileri çeker ve kaydeder.
        
        Bu metod:
        1. settings.toml'dan EVDS ayarlarını okur
        2. Tanımlanan tüm serileri çeker
        3. Tek bir DataFrame'de birleştirir
        4. data/raw/macro/ dizinine CSV olarak kaydeder
        
        Args:
            output_filename (str): Çıktı dosya adı. Varsayılan: "evds_macro_daily.csv"
        
        Returns:
            str: Kaydedilen dosyanın tam yolu
            
        Raises:
            ValueError: EVDS ayarları eksikse
        """
        logger.info("Varsayılan makro veriler çekiliyor...")
        
        # EVDS ayarlarını oku
        evds_settings = get_evds_settings()
        
        if not evds_settings:
            raise ValueError(
                "EVDS ayarları config/settings.toml dosyasında bulunamadı"
            )
        
        start_date = evds_settings.get("start_date")
        end_date = evds_settings.get("end_date")
        series_dict = evds_settings.get("series", {})
        
        if not start_date or not end_date:
            raise ValueError(
                "start_date ve end_date config/settings.toml dosyasında tanımlanmalı"
            )
        
        if not series_dict:
            raise ValueError(
                "Çekilecek seri bulunamadı. config/settings.toml içinde [evds.series] "
                "bölümünü kontrol edin"
            )
        
        # Seri kodlarını ve isimlerini ayır
        series_mapping = {}  # friendly_name -> evds_code
        for friendly_name, evds_code in series_dict.items():
            if evds_code:  # Boş olmayan kodları al
                series_mapping[friendly_name] = evds_code
        
        if not series_mapping:
            logger.warning("Çekilecek geçerli seri kodu bulunamadı")
            return ""
        
        logger.info(f"Toplam {len(series_mapping)} seri çekilecek")
        
        # Tüm serileri çek
        all_series_codes = list(series_mapping.values())
        df = self.fetch_series(
            series_codes=all_series_codes,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            logger.warning("Hiç veri çekilemedi")
            return ""
        
        # Kolon isimlerini düzenle (EVDS kod -> friendly name)
        # evdspy genellikle seri kodlarını TP_DK_USD_A_YTL gibi underscore'lu döndürür
        reverse_mapping = {code: name for name, code in series_mapping.items()}
        
        # Mevcut kolonları kontrol et ve yeniden adlandır
        rename_dict = {}
        for col in df.columns:
            # EVDS kodu ile eşleşme ara
            for evds_code, friendly_name in reverse_mapping.items():
                # Hem noktasız hem noktalı versiyonları kontrol et
                code_underscore = evds_code.replace(".", "_")
                if col == evds_code or col == code_underscore or evds_code in col:
                    rename_dict[col] = friendly_name
                    break
        
        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.info(f"Kolonlar yeniden adlandırıldı: {list(rename_dict.values())}")
        
        # Dosya yolunu oluştur
        output_path = MACRO_DATA_DIR / output_filename
        
        # CSV olarak kaydet
        df.to_csv(output_path, encoding="utf-8")
        logger.info(f"Veri başarıyla kaydedildi: {output_path}")
        logger.info(f"Toplam {len(df)} satır, {len(df.columns)} kolon")
        
        # İlk birkaç satırı göster
        logger.info(f"\nİlk 3 satır:\n{df.head(3)}")
        
        return str(output_path)
