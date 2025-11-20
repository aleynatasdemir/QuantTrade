from isyatirimhisse import fetch_financials
import pandas as pd
from pathlib import Path
import time
import logging
import sys
import tomllib
import random

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ------------------------------------------------------------------
# 1) Hisse listesini config/settings.toml'den al
# ------------------------------------------------------------------
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "settings.toml"

try:
    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)
    symbols = config.get("stocks", {}).get("symbols", [])
    
    if not symbols:
        logging.error("Config'te hisse listesi (stocks.symbols) bulunamadı!")
        sys.exit(1)
        
except FileNotFoundError:
    logging.error(f"Config dosyası bulunamadı: {CONFIG_PATH}")
    sys.exit(1)
except Exception as e:
    logging.error(f"Config dosyası okunurken hata: {e}")
    sys.exit(1)

# Benzersiz sembolleri al (duplikatları çıkar)
symbols = list(set(symbols))
symbols.sort()

logging.info(f"{len(symbols)} adet sembol bulundu (config'ten yüklendi).")

# Proje kök dizinine göre ayarla (3 seviye yukarı: data_sources -> quanttrade -> src -> root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"

# Config'ten tarih aralığını oku
start_date_str = config.get("stocks", {}).get("start_date", "2020-01-01")
end_date_str = config.get("stocks", {}).get("end_date", "2025-11-17")

# Tarih aralığını parse et (YYYY-MM-DD formatında)
from datetime import datetime
start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

# Yılları ayıkla
start_year = start_date.year
end_year = end_date.year

logging.info(f"Tarih aralığı: {start_date_str} -> {end_date_str}")
logging.info(f"Yıl aralığı: {start_year} -> {end_year}")

# fetch_financials parametreleri
EXCHANGE = "USD"         # a.py'de USD kullanıyorsun
FINANCIAL_GROUP = "1"    # Gelir Tablosu (Income Statement)

no_data = []

# ------------------------------------------------------------------
# 2) Her hisse için İş Yatırım finansal verisini çek (yıl yıl) ve kaydet
# ------------------------------------------------------------------
for i, sym in enumerate(symbols, start=1):
    logging.info(f"\n[{i}/{len(symbols)}] {sym} için finansal veriler çekiliyor ({start_year}-{end_year})...")
    
    # Bu sembol için tüm yıllardan veri topla
    all_years_data = []
    metadata_cols = None  # Metadata sütunlarını saklayacağız
    
    for year in range(start_year, end_year + 1):
        logging.info(f"  → {sym}: {year} verisi çekiliyor...")
        
        max_retries = 3
        retry_count = 0
        financial_data_output = None
        success = False
        
        while retry_count < max_retries and not success:
            try:
                financial_data_output = fetch_financials(
                    symbols=[sym],
                    start_year=str(year),
                    end_year=str(year),  # Max 4 çeyrek: sadece bu sene
                    exchange=EXCHANGE,
                    financial_group=FINANCIAL_GROUP,
                    save_to_excel=False,
                )
                success = True  # Başarılı olduysa bayrağı set et
                break  # Başarılı olduysa döngüden çık
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 + random.uniform(0, 2)  # 2-4 saniye random bekleme
                    logging.warning(f"    {sym} ({year}): Deneme {retry_count}/{max_retries} başarısız, {wait_time:.1f}s bekleniyor...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"    {sym} ({year}): {max_retries} deneme sonrası başarısız: {e}")

        # a.py'deki gibi: bazen list, bazen direkt DataFrame dönebiliyor
        df_year = None
        if financial_data_output is not None and isinstance(financial_data_output, list):
            if not financial_data_output:
                logging.debug(f"    {sym} ({year}): boş liste döndü.")
            else:
                df_year = financial_data_output[0]
        elif isinstance(financial_data_output, pd.DataFrame):
            df_year = financial_data_output
        else:
            logging.debug(
                f"    {sym} ({year}): beklenmedik tip döndürdü: {type(financial_data_output)}"
            )

        if df_year is not None and not df_year.empty:
            # İlk yıldaysa metadata sütunlarını kaydet
            if metadata_cols is None:
                metadata_cols = [col for col in df_year.columns if col in 
                    ['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN', 'SYMBOL']]
            
            all_years_data.append(df_year)
            logging.info(f"    ✓ {sym} ({year}): {len(df_year)} satır")
        
        # Her istek sonrası daha uzun bekleme (rate limiting'i önlemek için)
        wait_time = 1.5 + random.uniform(0.5, 1.5)  # 2-3 saniye random bekleme
        time.sleep(wait_time)

    # Tüm yılların verilerini birleştir
    if not all_years_data:
        logging.warning(f"{sym}: hiç veri çekilemedi")
        no_data.append(sym)
        continue

    # Metadata sütunlarını ayarla (her DataFrame'de olması lazım)
    metadata_cols = ['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN', 'SYMBOL']
    
    if len(all_years_data) == 1:
        df_raw = all_years_data[0]
    else:
        # İlk DataFrame'i başlangıç olarak set et
        df_raw = all_years_data[0][metadata_cols].copy()
        
        # Tüm yılların sayısal sütunlarını (çeyrek verileri) toplayıp ekle
        all_quarters = {}
        for df_year in all_years_data:
            # Metadata olmayan sütunları al (bu çeyrek sütunları)
            quarter_cols = [col for col in df_year.columns if col not in metadata_cols]
            for col in quarter_cols:
                all_quarters[col] = df_year[col].values
        
        # Sayısal sütunları DataFrame'e ekle
        for col_name, col_data in all_quarters.items():
            df_raw[col_name] = col_data
    
    # Duplikatları çıkar (farklı yıllardan tekrar gelme ihtimali)
    df_raw = df_raw.drop_duplicates(ignore_index=True)
    
    logging.info(f"{sym}: Toplam {len(df_raw)} satır (tüm yıllar birleştirildi)")

    # --------------------------------------------------------------
    # Kaydetme: data/mali_tablo/{SYMBOL}.csv
    # --------------------------------------------------------------
    out_dir = BASE_DIR / "mali_tablo"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{sym}.csv"
    df_raw.to_csv(out_path, index=False, encoding="utf-8-sig")
    logging.info(f"✓ {sym}: kaydedildi -> {out_path}")

# ------------------------------------------------------------------
# 3) Hiç veri çekilemeyen sembolleri logla
# ------------------------------------------------------------------
if no_data:
    nd_path = BASE_DIR / "mali_tablo_no_data_symbols.csv"
    pd.Series(no_data, name="symbol").to_csv(nd_path, index=False)
    logging.warning(f"Hiç finansal veri bulunamayan hisseler -> {nd_path}")
else:
    logging.info("Tüm semboller için en az bir miktar finansal veri bulundu.")
