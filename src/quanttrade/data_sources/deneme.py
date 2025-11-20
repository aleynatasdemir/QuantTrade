# import requests  <-- BUNU KALDIRIYORUZ
from curl_cffi import requests  # <-- YENİ KÜTÜPHANE (Browser Impersonation)
import json
import csv
import sys
import time
import random  # <-- Rastgelelik için
from pathlib import Path

BASE_URL = "https://www.kap.org.tr"

# Output klasörünü ayarla
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "announcements"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Config ve mapping dosyaları
sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols

MAPPING_FILE = PROJECT_ROOT / "config" / "kap_symbols_oids_mapping.json"

# ---- YENİ SESSION OLUŞTURUCU ----
def create_browser_session():
    """Gerçek bir Chrome tarayıcısını taklit eden session oluşturur."""
    sess = requests.Session(impersonate="chrome120") # Chrome 120 taklidi
    
    # Sadece genel headerlar, Cookie yok! Cookie'yi site verecek.
    sess.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/tr/bildirim-sorgu",
    })
    
    # İlk bağlantıyı kurup Cookie'leri toplamak için anasayfaya git
    try:
        sess.get(BASE_URL, timeout=10)
        time.sleep(1)
    except:
        pass
        
    return sess

# Global Session
session = create_browser_session()

def fetch_financial_reports(from_date, to_date, oid):
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

    max_retries = 5  # Deneme sayısını artırdık
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Her istekten önce rastgele bekle (2-4 saniye)
            time.sleep(random.uniform(2.0, 4.0))

            r = session.post(url, data=json.dumps(payload), timeout=30)

            # Status Code Kontrolü (429 gelirse direk yakala)
            if r.status_code == 429:
                print(f"\n⛔ Hız Sınırı (429)! 60 saniye soğuma bekleniyor... (Deneme {retry_count+1}/{max_retries})")
                time.sleep(60) # 1 Dakika ceza beklemesi
                session = create_browser_session() # Yeni kimlik al
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
                if not isinstance(item, dict): continue
                subject = (item.get("subject") or "").strip()
                if "Finansal" not in subject: continue

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

def generate_year_ranges(start_year, end_year):
    year_ranges = []
    for year in range(start_year, end_year + 1):
        year_ranges.append((f"{year}-01-01", f"{year}-12-31"))
    return year_ranges

if __name__ == "__main__":
    print("=" * 70)
    print("KAP ANNOUNCEMENT SCRAPER (ANTI-DETECT MODE)")
    print("=" * 70)
    
    START_YEAR = 2020
    END_YEAR = 2025
    
    symbol_oid_map = load_symbol_oid_mapping()
    year_ranges = generate_year_ranges(START_YEAR, END_YEAR)
    
    print(f"   ✓ {len(symbol_oid_map)} sembol taranacak")
    
    success_count = 0
    
    for i, (symbol, oid) in enumerate(symbol_oid_map.items()):
        print(f"[{i+1}/{len(symbol_oid_map)}] {symbol}...", end=" ", flush=True)
        
        all_reports = []
        
        try:
            for start_date, end_date in year_ranges:
                reports = fetch_financial_reports(start_date, end_date, oid)
                all_reports.extend(reports)
                
                # Yıllar arasında rastgele bekleme (İnsan davranışı)
                time.sleep(random.uniform(1.0, 2.5))
            
            if all_reports:
                csv_file = OUTPUT_DIR / f"{symbol}_announcements.csv"
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["index", "publishDate", "ruleType", "summary", "url"])
                    writer.writeheader()
                    writer.writerows(all_reports)
                print(f"✓ {len(all_reports)} rapor")
                success_count += 1
            else:
                print("⚠ Veri yok")
            
            # Semboller arasında DAHA UZUN ve RASTGELE bekleme
            # Burası kritik: Sabit 2 saniye yerine 3 ile 7 saniye arası bekle
            wait_time = random.uniform(3.0, 7.0)
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Kritik Hata: {e}")
            time.sleep(10) # Hata olursa uzun bekle