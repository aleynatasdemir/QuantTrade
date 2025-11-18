import requests
import json
import csv
import sys
import time
from pathlib import Path

BASE_URL = "https://www.kap.org.tr"

# Output klasörünü ayarla
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "announcements"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Config ve mapping dosyaları
sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols, get_stock_date_range

MAPPING_FILE = PROJECT_ROOT / "config" / "kap_symbols_oids_mapping.json"

session = requests.Session()

# ---- TARAYICIDAKİ HEADER'LAR ----
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "tr",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/tr/bildirim-sorgu",
    "Connection": "keep-alive"
})

# ---- TARAYICIDAKİ COOKIES ----
session.cookies.update({
    "_ga": "GA1.1.1971839622.1763387350",
    "NSC_xxx.lbq.psh.us_tjuf_zfoj": "7ce2a3d9ddad9f0439920efb260b36acad4a64f3df2ef79bda6c88b7f8de60bb9ae4e5ca",
    "client-ip": "37.155.237.157",
    "AGVY-Cookie": "MDMAAAEAvBguNwAAAAAlm-2djnkbaeb4PmTz6i_1VcrApsoTC0adSVmIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAANJU3iUELHuU3YPc7e6186NEnO7wbnsbaQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGXTvuiWQoTLRasivtt9WFFUeGb2",
    "_ga_L21W6S1YS4": "GS2.1.s1763408718$o5$g1$t1763408731$j47$l0$h0",
    "KAP": "AAM7rmgbaTt9OgIFAAAAADsUL9ZOBg_0wi2-O8Ucf59ZvO9ZE3i4E3jsfRfl63eOOw==q3wbaQ==7LwOrLySjcObzxZmUdnwz9gwTCQ=",
    "KAP_.kap.org.tr_%2F_wlf": (
        "AAAAAAVhZ0s_Z-eBkcna46s7Uqky6qOodcTNJ2AJARlCnjmdhSPVzFDibUYjZ9__iMzE-HKHQwIuH7Rswvrxr-"
        "J88uZ4OOFdLemWzpRjALCkQkFFWf-rH_c2u5vs9Qx1qGkm6ZY=&AAAAAAXch89U54zYeZPrzcYEk9eWOAm2Sy"
        "MtPjPDPvwfXYEI9dAzX4VjBdjTD5kPeBk3jQyJpIj7cJCuz_8i2xBAUZnx&"
    ),
})


def fetch_financial_reports(from_date, to_date, oid):
    url = BASE_URL + "/tr/api/disclosure/members/byCriteria"

    # ---- BİREBİR SEND PAYLOAD ----
    payload = {
        "fromDate": from_date,
        "toDate": to_date,
        "memberType": "IGS",
        "disclosureClass": "FR",  # Finansal Rapor
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

    r = session.post(url, data=json.dumps(payload), timeout=20)

    try:
        data = r.json()
    except:
        print("❌ JSON parse edilemedi:", r.text[:300])
        return []

    # ---- API BAŞARISIZSA ----
    if isinstance(data, dict) and (not data.get("success", True)):
        print("❌ API hata:", data)
        return []

    if not isinstance(data, list):
        print("❌ Beklenen list ama gelen:", type(data))
        print(json.dumps(data, indent=2, ensure_ascii=False))
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
            "ruleType": item.get("ruleType"),  # 3 Aylık, 6 Aylık, 9 Aylık, Yıllık
            "summary": item.get("summary"),
            "url": f"https://www.kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}"
        })

    return results


def load_symbol_oid_mapping():
    """Config'ten semboller ve mapping'ten OID'leri yükle"""
    # Config'ten semboller
    symbols = get_stock_symbols()
    
    # Mapping dosyasından OID'ler
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping_data = json.load(f)
    
    companies = mapping_data.get("companies", {})
    
    # Eşleştir
    symbol_oid_map = {}
    for symbol in symbols:
        symbol_upper = symbol.upper()
        if symbol_upper in companies:
            symbol_oid_map[symbol_upper] = companies[symbol_upper]["oid"]
    
    return symbol_oid_map


def generate_year_ranges(start_year, end_year):
    """Yıl aralıklarını oluştur"""
    year_ranges = []
    for year in range(start_year, end_year + 1):
        year_ranges.append((f"{year}-01-01", f"{year}-12-31"))
    return year_ranges


# ---- KULLANIM ----
if __name__ == "__main__":
    print("=" * 70)
    print("KAP ANNOUNCEMENT SCRAPER")
    print("=" * 70)
    
    # Tarih aralığı ayarla
    START_YEAR = 2020
    END_YEAR = 2025
    
    # Mapping yükle
    print("\n📋 Sembol-OID eşleştirmesi yükleniyor...")
    symbol_oid_map = load_symbol_oid_mapping()
    
    print(f"   ✓ {len(symbol_oid_map)} sembol eşleştirildi")
    print(f"   ✓ Tarih aralığı: {START_YEAR} - {END_YEAR}")
    
    # Yıl aralıklarını oluştur
    year_ranges = generate_year_ranges(START_YEAR, END_YEAR)
    print(f"   ✓ {len(year_ranges)} yıl aralığı oluşturuldu")
    
    # Her sembol için anons çek
    print("\n🔍 Anonslar çekiliyor...\n")
    
    success_count = 0
    fail_count = 0
    
    for symbol, oid in symbol_oid_map.items():
        print(f"   {symbol}...", end=" ", flush=True)
        
        all_reports = []  # Tüm yılların raporlarını topla
        
        try:
            # Her yıl için ayrı ayrı çek
            for start_date, end_date in year_ranges:
                reports = fetch_financial_reports(start_date, end_date, oid)
                all_reports.extend(reports)
                time.sleep(1)  # Yıllar arası kısa bekleme
            
            if all_reports:
                csv_file = OUTPUT_DIR / f"{symbol}_announcements.csv"
                
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["index", "publishDate", "ruleType", "summary", "url"])
                    writer.writeheader()
                    writer.writerows(all_reports)
                
                print(f"✓ {len(all_reports)} rapor")
                success_count += 1
            else:
                print("⚠ Rapor yok")
                fail_count += 1
            
            # Rate limiting - semboller arası
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Hata: {e}")
            fail_count += 1
            time.sleep(3)
    
    # Özet
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print(f"Toplam sembol: {len(symbol_oid_map)}")
    print(f"Başarılı: {success_count}")
    print(f"Başarısız/Boş: {fail_count}")
    print(f"Yıl aralığı: {START_YEAR}-{END_YEAR} ({len(year_ranges)} yıl)")
    print(f"Klasör: {OUTPUT_DIR}")
    print("=" * 70)
