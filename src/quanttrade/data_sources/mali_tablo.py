"""
Mali Tablo (Finansal Tablo) Downloader - INCREMENTAL MOD

INCREMENTAL LOGIC:
- Her sembol için mevcut CSV dosyasına bakar
- Mevcut dönemlere (çeyreklere) bakar
- Sadece eksik yıl/çeyrek verilerini çeker
- Eski veriyle birleştirir
"""

from isyatirimhisse import fetch_financials
import pandas as pd
from pathlib import Path
import time
import logging
import sys
import random
from datetime import datetime

# Python 3.11+ has tomllib built-in, older versions need tomli
try:
    import tomllib
except ImportError:
    import tomli as tomllib

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

# Proje kök dizinine göre ayarla
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"


def get_last_business_day(date: datetime = None) -> datetime:
    """Haftasonu ise Cuma'ya geri gider."""
    if date is None:
        date = datetime.now()
    while date.weekday() >= 5:
        from datetime import timedelta
        date -= timedelta(days=1)
    return date


# Config'ten tarih aralığını oku
start_date_str = config.get("stocks", {}).get("start_date", "2020-01-01")
# end_date otomatik olarak son iş günü
end_date = get_last_business_day()
end_date_str = end_date.strftime("%Y-%m-%d")

# Tarih aralığını parse et (YYYY-MM-DD formatında)
start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

# Yılları ayıkla
start_year = start_date.year
end_year = end_date.year

logging.info(f"Tarih aralığı: {start_date_str} -> {end_date_str} (otomatik son iş günü)")
logging.info(f"Yıl aralığı: {start_year} -> {end_year}")

# fetch_financials parametreleri
EXCHANGE = "USD"
FINANCIAL_GROUP = "1"  # Gelir Tablosu (Income Statement)

# Metadata sütunları (bunlar çeyrek değil sabit sütunlar)
METADATA_COLS = ['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 'FINANCIAL_ITEM_NAME_EN', 'SYMBOL']


def get_existing_quarters(file_path):
    """
    Mevcut CSV dosyasındaki çeyrek dönemleri tespit eder.
    Çeyrek sütunları genelde YYYY/Q formatında olur (örn: 2023/3, 2024/12).
    
    Returns:
        tuple: (years_set, quarters_set, dataframe)
    """
    if not file_path.exists():
        return set(), set(), None
    
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        if df.empty:
            return set(), set(), None
        
        # Metadata olmayan sütunlar çeyrek sütunlarıdır
        quarter_cols = [col for col in df.columns if col not in METADATA_COLS]
        
        # Çeyrek sütunlarından yıl ve çeyrek bilgisini çıkar (örn: "2023/3" -> year=2023, quarter=3)
        years = set()
        quarters = set()  # (year, quarter) tuple'ları
        for col in quarter_cols:
            try:
                # Format: YYYY/MM veya YYYY/Q
                if '/' in str(col):
                    parts = str(col).split('/')
                    year = int(parts[0])
                    quarter = int(parts[1])
                    years.add(year)
                    quarters.add((year, quarter))
            except:
                pass
        
        return years, quarters, df
    except Exception as e:
        logging.warning(f"Dosya okuma hatası: {e}")
        return set(), set(), None


def get_last_quarter_in_file(file_path):
    """
    Mevcut dosyadaki en son çeyreği döndürür.
    
    Returns:
        tuple: (year, quarter) or None
    """
    _, quarters, _ = get_existing_quarters(file_path)
    if quarters:
        # En son çeyreği bul (önce yıl, sonra çeyrek numarasına göre sırala)
        return max(quarters, key=lambda x: (x[0], x[1]))
    return None


def get_expected_quarter():
    """
    Bugünün tarihine göre mevcut olması beklenen en güncel çeyreği döndürür.
    
    Finansal raporlar genelde çeyrek bitiminden ~2 ay sonra açıklanır:
    - Q1 (Mart sonu): Mayıs'ta açıklanır
    - Q2 (Haziran sonu): Ağustos'ta açıklanır  
    - Q3 (Eylül sonu): Kasım'da açıklanır
    - Q4 (Aralık sonu): Şubat/Mart'ta açıklanır
    
    Returns:
        tuple: (year, quarter_month) örn: (2024, 9) = 2024 Q3
    """
    today = datetime.now()
    year = today.year
    month = today.month
    
    # Hangi çeyreğin verileri şu an mevcut olmalı?
    # 2 ay gecikme varsayımı ile:
    if month >= 11:  # Kasım-Aralık: Q3 mevcut olmalı
        return (year, 9)
    elif month >= 8:  # Ağustos-Ekim: Q2 mevcut olmalı
        return (year, 6)
    elif month >= 5:  # Mayıs-Temmuz: Q1 mevcut olmalı
        return (year, 3)
    elif month >= 3:  # Mart-Nisan: Geçen yılın Q4 mevcut olmalı
        return (year - 1, 12)
    else:  # Ocak-Şubat: Geçen yılın Q3 mevcut olmalı
        return (year - 1, 9)


def is_quarter_up_to_date(file_path):
    """
    Dosyadaki en son çeyreğin güncel olup olmadığını kontrol eder.
    
    Returns:
        tuple: (is_up_to_date: bool, last_quarter: tuple or None, expected_quarter: tuple)
    """
    last_quarter = get_last_quarter_in_file(file_path)
    expected_quarter = get_expected_quarter()
    
    if last_quarter is None:
        return False, None, expected_quarter
    
    # Çeyrek karşılaştırması: (year, quarter)
    last_key = (last_quarter[0], last_quarter[1])
    expected_key = (expected_quarter[0], expected_quarter[1])
    
    is_current = last_key >= expected_key
    return is_current, last_quarter, expected_quarter


def get_last_year_in_file(file_path):
    """Mevcut dosyadaki en son yılı döndürür (backward compatibility)."""
    existing_years, _, _ = get_existing_quarters(file_path)
    if existing_years:
        return max(existing_years)
    return None


def merge_financial_data(old_df, new_dfs):
    """
    Eski ve yeni finansal verileri birleştirir.
    Çeyrek sütunlarını horizontal olarak birleştirir.
    """
    if not new_dfs:
        return old_df
    
    if old_df is None or old_df.empty:
        # Sadece yeni veriyi birleştir
        if len(new_dfs) == 1:
            return new_dfs[0]
        
        combined = new_dfs[0][METADATA_COLS].copy() if METADATA_COLS[0] in new_dfs[0].columns else new_dfs[0].copy()
        all_quarters = {}
        
        for df in new_dfs:
            quarter_cols = [col for col in df.columns if col not in METADATA_COLS]
            for col in quarter_cols:
                if col not in all_quarters:
                    all_quarters[col] = df[col].values
        
        for col_name, col_data in all_quarters.items():
            combined[col_name] = col_data
        
        return combined
    
    # Eski veri var, yeni verileri ekle
    combined = old_df.copy()
    
    for new_df in new_dfs:
        quarter_cols = [col for col in new_df.columns if col not in METADATA_COLS]
        for col in quarter_cols:
            if col not in combined.columns:
                # Satır sayıları eşleşmeli
                if len(new_df) == len(combined):
                    combined[col] = new_df[col].values
                else:
                    # Satır sayısı farklıysa merge yap
                    logging.warning(f"Satır sayısı farklı: {len(combined)} vs {len(new_df)}")
    
    return combined


def fetch_single_year(sym, year, retries=3):
    """Tek bir yıl için finansal veri çeker."""
    for attempt in range(retries):
        try:
            result = fetch_financials(
                symbols=[sym],
                start_year=str(year),
                end_year=str(year),
                exchange=EXCHANGE,
                financial_group=FINANCIAL_GROUP,
                save_to_excel=False,
            )
            
            if isinstance(result, list) and result:
                return result[0]
            elif isinstance(result, pd.DataFrame):
                return result
            return None
            
        except Exception as e:
            if attempt < retries - 1:
                wait_time = 2 + random.uniform(0, 2)
                logging.warning(f"    {sym} ({year}): Deneme {attempt+1}/{retries} başarısız, {wait_time:.1f}s bekleniyor...")
                time.sleep(wait_time)
            else:
                logging.error(f"    {sym} ({year}): {retries} deneme sonrası başarısız: {e}")
    return None


no_data = []
skip_count = 0
update_count = 0

# ------------------------------------------------------------------
# 2) Her hisse için incremental finansal veri çek
# ------------------------------------------------------------------
logging.info("\n" + "=" * 70)
logging.info("MALI TABLO DOWNLOADER (INCREMENTAL MOD)")
logging.info("=" * 70)
logging.info("NOT: Her sembol için mevcut veri kontrol edilecek.")
logging.info("     Sadece eksik yılların verileri çekilecek.\n")

for i, sym in enumerate(symbols, start=1):
    out_dir = BASE_DIR / "mali_tablo"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sym}.csv"
    
    # Çeyrek bazlı güncellik kontrolü
    is_current, last_quarter, expected_quarter = is_quarter_up_to_date(out_path)
    
    # Hangi yılları çekmemiz gerekiyor?
    current_year = datetime.now().year
    target_end_year = min(end_year, current_year)
    
    if is_current:
        # Veri güncel - çeyrek bazlı kontrol
        last_q_str = f"{last_quarter[0]}/Q{last_quarter[1]//3}" if last_quarter else "?"
        expected_q_str = f"{expected_quarter[0]}/Q{expected_quarter[1]//3}"
        logging.info(f"[{i}/{len(symbols)}] {sym}: ✓ Güncel (son: {last_q_str}, beklenen: {expected_q_str})")
        skip_count += 1
        time.sleep(0.3)
        continue
    
    # Mevcut dosyayı oku
    _, _, old_df = get_existing_quarters(out_path)
    last_year = get_last_year_in_file(out_path)
    
    # İncremental: son yıldan itibaren çek
    if last_year is not None:
        years_to_fetch = list(range(last_year, target_end_year + 1))
        last_q_str = f"{last_quarter[0]}/Q{last_quarter[1]//3}" if last_quarter else "?"
        expected_q_str = f"{expected_quarter[0]}/Q{expected_quarter[1]//3}"
        logging.info(f"[{i}/{len(symbols)}] {sym}: Incremental (son: {last_q_str}, hedef: {expected_q_str})...")
    else:
        years_to_fetch = list(range(start_year, target_end_year + 1))
        expected_q_str = f"{expected_quarter[0]}/Q{expected_quarter[1]//3}"
        logging.info(f"[{i}/{len(symbols)}] {sym}: Full ({start_year} -> hedef: {expected_q_str})...")
    
    # Yıl yıl veri çek
    new_data = []
    
    for year in years_to_fetch:
        df_year = fetch_single_year(sym, year)
        
        if df_year is not None and not df_year.empty:
            new_data.append(df_year)
            logging.info(f"    ✓ {sym} ({year}): {len(df_year)} satır")
        
        # Rate limiting
        wait_time = 1.5 + random.uniform(0.5, 1.5)
        time.sleep(wait_time)
    
    # Veri birleştir ve kaydet
    if not new_data and (old_df is None or old_df.empty):
        logging.warning(f"{sym}: hiç veri çekilemedi")
        no_data.append(sym)
        continue
    
    # Merge
    combined = merge_financial_data(old_df, new_data)
    
    if combined is not None and not combined.empty:
        # Duplikatları çıkar
        combined = combined.drop_duplicates(ignore_index=True)
        
        # Kaydet
        combined.to_csv(out_path, index=False, encoding="utf-8-sig")
        
        quarter_count = len([c for c in combined.columns if c not in METADATA_COLS])
        if last_year:
            logging.info(f"    ✓ {sym}: Güncellendi ({quarter_count} dönem)")
        else:
            logging.info(f"    ✓ {sym}: Kaydedildi ({quarter_count} dönem)")
        update_count += 1
    else:
        logging.warning(f"{sym}: birleştirme sonrası boş veri")

# ------------------------------------------------------------------
# 3) Özet
# ------------------------------------------------------------------
logging.info("\n" + "=" * 70)
logging.info("ÖZET")
logging.info("=" * 70)
logging.info(f"Toplam sembol: {len(symbols)}")
logging.info(f"Atlanan (güncel): {skip_count}")
logging.info(f"Güncellenen/Yeni: {update_count}")
logging.info(f"Başarısız: {len(no_data)}")

if no_data:
    nd_path = BASE_DIR / "mali_tablo_no_data_symbols.csv"
    pd.Series(no_data, name="symbol").to_csv(nd_path, index=False)
    logging.warning(f"Hiç finansal veri bulunamayan hisseler -> {nd_path}")
else:
    logging.info("Tüm semboller için en az bir miktar finansal veri bulundu.")
    
logging.info("=" * 70)
