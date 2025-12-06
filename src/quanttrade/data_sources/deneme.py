"""
KAP Announcement Scraper - INCREMENTAL MOD

INCREMENTAL LOGIC:
- Her sembol için mevcut CSV dosyasına bakar
- Son duyuru tarihinden sonraki yeni duyuruları çeker
- Eski veriyle birleştirir, duplikatları temizler
"""

from curl_cffi import requests
import json
import csv
import sys
import time
import random
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_URL = "https://www.kap.org.tr"

# Output klasörünü ayarla
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "announcements"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Config ve mapping dosyaları
sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols, get_stock_date_range

MAPPING_FILE = PROJECT_ROOT / "config" / "kap_symbols_oids_mapping.json"


def create_browser_session():
    """Gerçek bir Chrome tarayıcısını taklit eden session oluşturur."""
    sess = requests.Session(impersonate="chrome120")
    
    sess.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/tr/bildirim-sorgu",
    })
    
    try:
        sess.get(BASE_URL, timeout=10)
        time.sleep(1)
    except:
        pass
        
    return sess


# Global Session
session = create_browser_session()


def fetch_financial_reports(from_date, to_date, oid):
    """Belirli tarih aralığı için finansal raporları çeker."""
    global session
    
    url = BASE_URL + "/tr/api/disclosure/members/byCriteria"

    payload = {
        "fromDate": from_date,
        "toDate": to_date,
        "memberType": "IGS",
        "disclosureClass": "FR",
        "mkkMemberOidList": [oid],
        "bdkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "disclosureIndexList": [],
        "subjectList": [],
        "ruleType": "",
        "period": "",
        "year": "",
        "sector": "",
        "mainSector": "",
        "subSector": "",
        "marketOid": "",
        "isLate": "",
        "term": "",
        "fromSrc": False,
        "index": "",
        "srcCategory": "",
        "bdkReview": ""
    }

    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            time.sleep(random.uniform(2.0, 4.0))

            r = session.post(url, data=json.dumps(payload), timeout=30)

            if r.status_code == 429:
                print(f"\n⛔ Hız Sınırı (429)! 60 saniye bekleniyor... (Deneme {retry_count+1}/{max_retries})")
                time.sleep(60)
                session = create_browser_session()
                retry_count += 1
                continue

            try:
                data = r.json()
            except:
                print(f"\n❌ JSON parse hatası! Status: {r.status_code}")
                time.sleep(10)
                session = create_browser_session()
                retry_count += 1
                continue
            
            if not data:
                time.sleep(5)
                retry_count += 1
                continue

            if isinstance(data, dict) and (not data.get("success", True)):
                return []

            if not isinstance(data, list):
                return []

            results = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                subject = (item.get("subject") or "").strip()
                if "Finansal" not in subject:
                    continue

                results.append({
                    "index": item.get("disclosureIndex"),
                    "publishDate": item.get("publishDate"),
                    "ruleType": item.get("ruleType"),
                    "summary": item.get("summary"),
                    "url": f"https://www.kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}"
                })

            return results
            
        except Exception as e:
            print(f"⚠ Bağlantı Hatası: {e}")
            time.sleep(10)
            session = create_browser_session()
            retry_count += 1
    
    print("❌ Bu aralık için veri çekilemedi (Tüm denemeler başarısız).")
    return []


def load_symbol_oid_mapping():
    """Sembol-OID eşleştirmesini yükler."""
    symbols = get_stock_symbols()
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping_data = json.load(f)
    companies = mapping_data.get("companies", {})
    symbol_oid_map = {}
    for symbol in symbols:
        symbol_upper = symbol.upper()
        if symbol_upper in companies:
            symbol_oid_map[symbol_upper] = companies[symbol_upper]["oid"]
    return symbol_oid_map


def get_last_announcement_date(file_path):
    """Mevcut dosyadaki son duyuru tarihini döndürür."""
    if not file_path.exists():
        return None
    
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        if df.empty or 'publishDate' not in df.columns:
            return None
        
        # Tarihleri parse et (format: DD.MM.YYYY HH:MM:SS - Türkçe format)
        df['publishDate'] = pd.to_datetime(df['publishDate'], dayfirst=True, errors='coerce')
        df = df[df['publishDate'].notna()]
        
        if df.empty:
            return None
        
        return df['publishDate'].max()
    except Exception as e:
        print(f"⚠ Dosya okuma hatası: {e}")
        return None


def merge_and_save_announcements(old_df, new_reports, file_path):
    """Eski ve yeni duyuruları birleştirir ve kaydeder."""
    new_df = pd.DataFrame(new_reports) if new_reports else pd.DataFrame()
    
    if old_df.empty and new_df.empty:
        return 0
    
    if old_df.empty:
        combined = new_df
    elif new_df.empty:
        combined = old_df
    else:
        combined = pd.concat([old_df, new_df], ignore_index=True)
    
    # Duplikatları temizle (index üzerinden - her duyuru unique index'e sahip)
    if 'index' in combined.columns:
        combined = combined.drop_duplicates(subset=['index'], keep='last')
    
    # Tarihe göre sırala
    if 'publishDate' in combined.columns:
        combined['_sort_date'] = pd.to_datetime(combined['publishDate'], errors='coerce')
        combined = combined.sort_values('_sort_date', ascending=False)
        combined = combined.drop('_sort_date', axis=1)
    
    combined = combined.reset_index(drop=True)
    
    # CSV olarak kaydet
    combined.to_csv(file_path, index=False, encoding='utf-8')
    
    return len(combined)


def generate_incremental_year_ranges(last_date, start_year, end_year):
    """Incremental çekim için yıl aralıklarını oluşturur."""
    if last_date is None:
        # Full çekim
        return [(f"{year}-01-01", f"{year}-12-31") for year in range(start_year, end_year + 1)]
    
    # Incremental: son tarihten itibaren
    last_year = last_date.year
    current_year = datetime.now().year
    
    year_ranges = []
    
    # Son tarihten o yılın sonuna kadar
    year_ranges.append((last_date.strftime("%Y-%m-%d"), f"{last_year}-12-31"))
    
    # Sonraki yıllar
    for year in range(last_year + 1, min(end_year, current_year) + 1):
        year_ranges.append((f"{year}-01-01", f"{year}-12-31"))
    
    return year_ranges


if __name__ == "__main__":
    print("=" * 70)
    print("KAP ANNOUNCEMENT SCRAPER (INCREMENTAL MOD)")
    print("=" * 70)
    
    # Config'ten tarih aralığı
    config_start_date, config_end_date = get_stock_date_range()
    START_YEAR = int(config_start_date.split("-")[0])
    END_YEAR = int(config_end_date.split("-")[0])
    
    symbol_oid_map = load_symbol_oid_mapping()
    
    print(f"\n   ✓ {len(symbol_oid_map)} sembol taranacak")
    print(f"   ✓ Config tarih aralığı: {config_start_date} - {config_end_date}")
    print("\n   NOT: Her sembol için mevcut veri kontrol edilecek.")
    print("        Sadece yeni duyurular çekilecek.\n")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for i, (symbol, oid) in enumerate(symbol_oid_map.items()):
        csv_file = OUTPUT_DIR / f"{symbol}_announcements.csv"
        
        # Mevcut dosyadaki son tarihi kontrol et
        last_date = get_last_announcement_date(csv_file)
        
        print(f"[{i+1}/{len(symbol_oid_map)}] {symbol}...", end=" ", flush=True)
        
        # Mevcut veriyi oku
        old_df = pd.DataFrame()
        if csv_file.exists():
            try:
                old_df = pd.read_csv(csv_file, encoding='utf-8')
            except:
                old_df = pd.DataFrame()
        
        # Config end date ile karşılaştır
        if last_date is not None:
            try:
                config_end_dt = datetime.strptime(config_end_date, "%Y-%m-%d")
                if last_date.date() >= config_end_dt.date():
                    print(f"✓ Güncel (son: {last_date.strftime('%Y-%m-%d')})")
                    skip_count += 1
                    time.sleep(0.5)
                    continue
            except:
                pass
        
        # Incremental yıl aralıkları
        year_ranges = generate_incremental_year_ranges(last_date, START_YEAR, END_YEAR)
        
        all_reports = []
        
        try:
            for start_date, end_date in year_ranges:
                reports = fetch_financial_reports(start_date, end_date, oid)
                all_reports.extend(reports)
                time.sleep(random.uniform(1.0, 2.5))
            
            if all_reports or not old_df.empty:
                # Yeni duyurular varsa filtrele
                if last_date is not None and all_reports:
                    # Sadece son tarihten sonraki duyuruları al
                    filtered_reports = []
                    for r in all_reports:
                        try:
                            pub_date = pd.to_datetime(r['publishDate'])
                            if pub_date > last_date:
                                filtered_reports.append(r)
                        except:
                            filtered_reports.append(r)
                    all_reports = filtered_reports
                
                total_count = merge_and_save_announcements(old_df, all_reports, csv_file)
                
                if last_date:
                    new_count = len(all_reports)
                    print(f"✓ +{new_count} yeni ({total_count} toplam)")
                else:
                    print(f"✓ {total_count} rapor")
                success_count += 1
            else:
                print("⚠ Veri yok")
                fail_count += 1
            
            # Semboller arasında bekleme
            wait_time = random.uniform(3.0, 7.0)
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Kritik Hata: {e}")
            fail_count += 1
            time.sleep(10)
    
    # Özet
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print(f"Toplam sembol: {len(symbol_oid_map)}")
    print(f"Başarılı (yeni/güncelleme): {success_count}")
    print(f"Atlanan (güncel): {skip_count}")
    print(f"Başarısız: {fail_count}")
    print(f"Klasör: {OUTPUT_DIR}")
    print("=" * 70)