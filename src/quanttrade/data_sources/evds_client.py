"""
EVDS Client - TCMB EVDS API ile veri çekme işlemlerini yönetir
"""

import pandas as pd
from typing import List, Dict, Optional, Union
from datetime import datetime
import logging

try:
    from evds import evdsAPI
except ImportError:
    # evds kurulu değilse, kullanıcıya bilgi ver
    evdsAPI = None

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
            ImportError: evds paketi kurulu değilse
            ValueError: API anahtarı geçersizse
        
        Not:
            5 Nisan 2024 tarihinde EVDS API güncellemesi yapılmıştır.
            API anahtarı artık HTTP header içinde gönderilmektedir.
        """
        if evdsAPI is None:
            raise ImportError(
                "evds paketi kurulu değil. Lütfen 'pip install evds --upgrade' komutunu çalıştırın."
            )
        
        self.api_key = api_key or get_evds_api_key()
        
        if not self.api_key:
            raise ValueError(
                "EVDS API anahtarı bulunamadı. Lütfen .env dosyasında EVDS_API_KEY tanımlayın."
            )
        
        try:
            # evds API client'ını oluştur
            # Not: API anahtarı constructor'da parametre olarak verilir
            # 5 Nisan 2024 güncellemesi: API anahtarı artık HTTP header'da gönderiliyor
            self.client = evdsAPI(self.api_key)
            logger.info("EVDS Client başarıyla oluşturuldu")
        except Exception as e:
            logger.error(f"EVDS Client oluşturulurken hata: {e}")
            raise
    
    def fetch_series(
        self, 
        series_codes: Union[str, List[str]], 
        start_date: str,
        end_date: str,
        aggregation_types: Optional[Union[str, List[str]]] = None,
        formulas: Optional[Union[str, List[int]]] = None,
        frequency: Optional[int] = None
    ) -> pd.DataFrame:
        """
        EVDS'ten belirtilen serileri çeker.
        
        Args:
            series_codes (str or List[str]): EVDS seri kodu veya kodları listesi
                Örnek: 'TP.DK.USD.A.YTL' veya ['TP.DK.USD.A.YTL', 'TP.DK.EUR.A.YTL']
            start_date (str): Başlangıç tarihi (YYYY-MM-DD veya DD-MM-YYYY formatında)
            end_date (str): Bitiş tarihi (YYYY-MM-DD veya DD-MM-YYYY formatında)
            aggregation_types (str or List[str], optional): Toplululaştırma yöntemi
                Seçenekler: 'avg', 'min', 'max', 'first', 'last', 'sum'
            formulas (str or List[int], optional): Formül
                1: Yüzde Değişim, 2: Fark, 3: Yıllık Yüzde Değişim
                4: Yıllık Fark, 5: Bir Önceki Yılın Sonuna Göre Yüzde Değişim
                6: Bir Önceki Yılın Sonuna Göre Fark, 7: Hareketli Ortalama, 8: Hareketli Toplam
            frequency (int, optional): Veri frekansı
                1: Günlük, 2: İşgünü, 3: Haftalık, 4: Ayda 2 Kez
                5: Aylık, 6: 3 Aylık, 7: 6 Aylık, 8: Yıllık
        
        Returns:
            pd.DataFrame: Tarih index'li DataFrame. Kolonlar seri kodlarıdır.
        
        Raises:
            ValueError: Geçersiz tarih formatı veya seri kodu
            
        Not:
            EVDS resmi paketi get_data() fonksiyonu DataFrame döndürür.
            Ham JSON verisine erişmek için client.data kullanılabilir.
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
            # İki formatı da destekle
            if "-" in start_date and len(start_date.split("-")[0]) == 4:
                # YYYY-MM-DD formatı
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                evds_start = start_dt.strftime("%d-%m-%Y")
                evds_end = end_dt.strftime("%d-%m-%Y")
            else:
                # DD-MM-YYYY formatı (zaten EVDS formatında)
                evds_start = start_date
                evds_end = end_date
        except ValueError as e:
            raise ValueError(
                f"Geçersiz tarih formatı. YYYY-MM-DD veya DD-MM-YYYY formatında olmalı. Hata: {e}"
            )
        
        logger.info(
            f"EVDS'ten {len(series_codes)} seri çekiliyor: "
            f"{', '.join(series_codes)} ({evds_start} - {evds_end})"
        )
        
        try:
            # EVDS API'den veri çek
            # Resmi evds paketi kullanımı:
            # get_data(series, startdate, enddate, aggregation_types, formulas, frequency)
            # NOT: Opsiyonel parametreler None yerine boş string ('') almalı
            df = self.client.get_data(
                series_codes,
                startdate=evds_start,
                enddate=evds_end,
                aggregation_types=aggregation_types if aggregation_types else '',
                formulas=formulas if formulas else '',
                frequency=frequency if frequency else ''
            )
            
            if df is None or df.empty:
                logger.warning("EVDS'ten veri çekilemedi veya sonuç boş")
                return pd.DataFrame()
            
            # Tarih sütununu düzenle
            # evds paketi genellikle 'Tarih' sütunu döndürür
            if 'Tarih' in df.columns:
                df = df.rename(columns={'Tarih': 'date'})
                # Farklı tarih formatlarını dene
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                # Geçerli tarihleri filtrele
                df = df[df['date'].notna()]
                if not df.empty:
                    df = df.set_index('date')
                    df = df.sort_index()
            
            # Numerik olmayan değerleri temizle
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
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
        2. Tanımlanan tüm serileri GÜNLÜK frekans ile çeker
        3. Aylık/yıllık serileri günlük aralıklara forward-fill ile doldurur
        4. Tek bir DataFrame'de birleştirir
        5. data/raw/macro/ dizinine CSV olarak kaydeder
        
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
        
        # Günlük tarih aralığı oluştur (business days - işgünleri)
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        daily_index = pd.date_range(start=start_dt, end=end_dt, freq='D')
        
        # Boş DataFrame oluştur
        df_combined = pd.DataFrame(index=daily_index)
        df_combined.index.name = 'date'
        
        # Her seri için ayrı ayrı çek ve birleştir
        # Bazı seriler sadece belirli frekanslarda mevcut
        series_frequencies = {
            # Döviz Kurları - Günlük (1)
            "TP.DK.USD.A.YTL": 1,
            "TP.DK.EUR.A.YTL": 1,
            # Enflasyon - Aylık (5)
            "TP.FG.J0": 5,
            # BIST100 - Günlük (1)
            "TP.MK.F.BILESIK": 1,
            # Para Arzı - Aylık (5)
            "TP.PBD.H09": 5,
            # TCMB Faiz - Aylık (5)
            "TP.YSSK.A1": 5,
            # ABD Verileri - Aylık (5)
            "TP.IMFCPIND.USA": 5,
            "TP.OECDONCU.USA": 5,
        }
        
        
        total_series = len(series_mapping)
        successful_series = 0
        
        for idx, (friendly_name, evds_code) in enumerate(series_mapping.items(), 1):
            # Compact log - sadece ilerleme
            if idx == 1 or idx == total_series:
                logger.info(f"📊 EVDS {idx}/{total_series} seri çekiliyor...")
            
            try:
                # Seri için uygun frekansı belirle
                freq = series_frequencies.get(evds_code, 1)  # Varsayılan: Günlük
                
                # Veri çek
                df_series = self.fetch_series(
                    series_codes=evds_code,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=freq
                )
                
                if df_series.empty:
                    logger.warning(f"⚠️  {friendly_name} - Veri yok")
                    continue
                
                # Kolon adını düzenle
                if len(df_series.columns) == 1:
                    df_series.columns = [friendly_name]
                else:
                    df_series = df_series.iloc[:, 0:1]
                    df_series.columns = [friendly_name]
                
                # Ana DataFrame'e ekle
                df_combined = df_combined.join(df_series, how='left')
                successful_series += 1
                
            except Exception as e:
                logger.error(f"❌ {friendly_name} - {str(e)[:50]}")
                continue
        
        logger.info(f"✅ EVDS: {successful_series}/{total_series} seri başarılı")
        
        if df_combined.empty or df_combined.shape[1] == 0:
            logger.warning("Hiç veri çekilemedi")
            return ""
        
        # Aylık/yıllık verileri günlük aralıklara forward-fill ile doldur
        logger.info("Eksik veriler forward-fill ile dolduruluyor...")
        df_combined = df_combined.ffill()
        
        # Başlangıçtaki NaN'ları backward-fill ile doldur
        df_combined = df_combined.bfill()
        
        # Hala NaN varsa 0 ile doldur
        df_combined = df_combined.fillna(0)
        
        # Dosya yolunu oluştur
        output_path = MACRO_DATA_DIR / output_filename
        
        # CSV olarak kaydet
        df_combined.to_csv(output_path, encoding="utf-8")
        logger.info(f"Veri başarıyla kaydedildi: {output_path}")
        logger.info(f"Toplam {len(df_combined)} satır, {len(df_combined.columns)} kolon")
        
        # İlk ve son birkaç satırı göster
        logger.info(f"\nİlk 5 satır:\n{df_combined.head()}")
        logger.info(f"\nSon 5 satır:\n{df_combined.tail()}")
        logger.info(f"\nVeri özeti:\n{df_combined.describe()}")
        
        return str(output_path)
