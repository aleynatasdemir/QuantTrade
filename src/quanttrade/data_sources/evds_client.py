"""
EVDS Client - TCMB EVDS API ile veri çekme işlemlerini yönetir (INCREMENTAL MOD)

INCREMENTAL LOGIC:
- Mevcut CSV dosyasındaki son tarihe bakar
- Sadece eksik günleri EVDS'ten çeker
- Eski veriyle birleştirir
"""

import pandas as pd
from typing import List, Dict, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import logging

try:
    from evds import evdsAPI
except ImportError:
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
        output_filename: str = "evds_macro_daily.csv",
        incremental: bool = True
    ) -> str:
        """
        settings.toml'da tanımlanan varsayılan makro serileri INCREMENTAL olarak çeker ve kaydeder.
        
        INCREMENTAL LOGIC:
        1. Mevcut dosyayı kontrol et
        2. Son tarihten itibaren sadece eksik günleri çek
        3. Eski veriyle birleştir
        
        Args:
            output_filename (str): Çıktı dosya adı. Varsayılan: "evds_macro_daily.csv"
            incremental (bool): True ise incremental, False ise full çekim
        
        Returns:
            str: Kaydedilen dosyanın tam yolu
        """
        logger.info("="*60)
        logger.info("EVDS Makro Veri Çekme (INCREMENTAL MOD)")
        logger.info("="*60)
        
        # EVDS ayarlarını oku
        evds_settings = get_evds_settings()
        
        if not evds_settings:
            raise ValueError("EVDS ayarları config/settings.toml dosyasında bulunamadı")
        
        config_start_date = evds_settings.get("start_date")
        config_end_date = evds_settings.get("end_date")
        series_dict = evds_settings.get("series", {})
        
        if not config_start_date or not config_end_date:
            raise ValueError("start_date ve end_date config/settings.toml dosyasında tanımlanmalı")
        
        if not series_dict:
            raise ValueError("Çekilecek seri bulunamadı")
        
        # Dosya yolunu oluştur
        output_path = MACRO_DATA_DIR / output_filename
        
        # INCREMENTAL: Mevcut dosyayı kontrol et
        old_df = pd.DataFrame()
        actual_start_date = config_start_date
        
        if incremental and output_path.exists():
            try:
                old_df = pd.read_csv(output_path, index_col=0, parse_dates=True)
                old_df.index.name = 'date'
                
                if not old_df.empty:
                    last_date = old_df.index.max()
                    
                    if isinstance(last_date, pd.Timestamp):
                        last_date = last_date.to_pydatetime()
                    
                    # Config end_date'i parse et
                    try:
                        end_dt = datetime.strptime(config_end_date, "%Y-%m-%d")
                    except ValueError:
                        end_dt = datetime.now()
                    
                    # Veri zaten güncel mi?
                    if last_date.date() >= end_dt.date():
                        logger.info(f"✓ Makro veri zaten güncel! Son tarih: {last_date.strftime('%Y-%m-%d')}")
                        return str(output_path)
                    
                    # Incremental başlangıç tarihi
                    new_start = last_date + timedelta(days=1)
                    actual_start_date = new_start.strftime("%Y-%m-%d")
                    
                    logger.info(f"Mevcut veri: {old_df.index.min().strftime('%Y-%m-%d')} - {last_date.strftime('%Y-%m-%d')}")
                    logger.info(f"Incremental çekim: {actual_start_date} -> {config_end_date}")
                    
            except Exception as e:
                logger.warning(f"Mevcut dosya okunamadı: {e}, full çekim yapılacak")
                old_df = pd.DataFrame()
                actual_start_date = config_start_date
        
        # Seri kodlarını ve isimlerini ayır
        series_mapping = {}
        for friendly_name, evds_code in series_dict.items():
            if evds_code:
                series_mapping[friendly_name] = evds_code
        
        if not series_mapping:
            logger.warning("Çekilecek geçerli seri kodu bulunamadı")
            return ""
        
        logger.info(f"Toplam {len(series_mapping)} seri çekilecek")
        logger.info(f"Tarih aralığı: {actual_start_date} -> {config_end_date}")
        
        # Günlük tarih aralığı oluştur
        start_dt = pd.to_datetime(actual_start_date)
        end_dt = pd.to_datetime(config_end_date)
        
        # Eğer çekilecek tarih aralığı yoksa
        if start_dt > end_dt:
            logger.info("Çekilecek yeni veri yok, mevcut veri güncel")
            return str(output_path)
        
        daily_index = pd.date_range(start=start_dt, end=end_dt, freq='D')
        
        # Yeni veri için DataFrame
        df_new = pd.DataFrame(index=daily_index)
        df_new.index.name = 'date'
        
        # Her seri için ayrı ayrı çek
        series_frequencies = {
            "TP.DK.USD.A.YTL": 1,
            "TP.DK.EUR.A.YTL": 1,
            "TP.FG.J0": 5,
            "TP.MK.F.BILESIK": 1,
            "TP.PBD.H09": 5,
            "TP.YSSK.A1": 5,
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
                freq = series_frequencies.get(evds_code, 1)
                
<<<<<<< HEAD
=======
                # Veri çek
>>>>>>> f253addf5f28e99f0d3a026638901b029d9ebe09
                df_series = self.fetch_series(
                    series_codes=evds_code,
                    start_date=actual_start_date,
                    end_date=config_end_date,
                    frequency=freq
                )
                
                if df_series.empty:
                    logger.warning(f"⚠️  {friendly_name} - Veri yok")
                    continue
                
                if len(df_series.columns) == 1:
                    df_series.columns = [friendly_name]
                else:
                    df_series = df_series.iloc[:, 0:1]
                    df_series.columns = [friendly_name]
                
<<<<<<< HEAD
                df_new = df_new.join(df_series, how='left')
                logger.info(f"✓ {friendly_name}: {len(df_series)} satır eklendi")
=======
                # Ana DataFrame'e ekle
                df_combined = df_combined.join(df_series, how='left')
                successful_series += 1
>>>>>>> f253addf5f28e99f0d3a026638901b029d9ebe09
                
            except Exception as e:
                logger.error(f"❌ {friendly_name} - {str(e)[:50]}")
                continue
        
<<<<<<< HEAD
        if df_new.empty or df_new.shape[1] == 0:
            logger.warning("Yeni veri çekilemedi")
            if not old_df.empty:
                return str(output_path)
=======
        logger.info(f"✅ EVDS: {successful_series}/{total_series} seri başarılı")
        
        if df_combined.empty or df_combined.shape[1] == 0:
            logger.warning("Hiç veri çekilemedi")
>>>>>>> f253addf5f28e99f0d3a026638901b029d9ebe09
            return ""
        
        # Eski ve yeni veriyi birleştir
        if not old_df.empty:
            logger.info("Eski ve yeni veri birleştiriliyor...")
            
            # Kolonları eşitle
            for col in old_df.columns:
                if col not in df_new.columns:
                    df_new[col] = None
            
            for col in df_new.columns:
                if col not in old_df.columns:
                    old_df[col] = None
            
            # Birleştir
            df_combined = pd.concat([old_df, df_new])
            
            # Duplikatları temizle (index üzerinden)
            df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
            
            # Sırala
            df_combined = df_combined.sort_index()
        else:
            df_combined = df_new
        
        # Forward-fill ve backward-fill
        logger.info("Eksik veriler dolduruluyor...")
        df_combined = df_combined.ffill()
        df_combined = df_combined.bfill()
        df_combined = df_combined.fillna(0)
        
        # Kaydet
        MACRO_DATA_DIR.mkdir(parents=True, exist_ok=True)
        df_combined.to_csv(output_path, encoding="utf-8")
        
        logger.info(f"✓ Veri kaydedildi: {output_path}")
        logger.info(f"  Toplam {len(df_combined)} satır, {len(df_combined.columns)} kolon")
        logger.info(f"  Tarih aralığı: {df_combined.index.min().strftime('%Y-%m-%d')} - {df_combined.index.max().strftime('%Y-%m-%d')}")
        
        return str(output_path)
