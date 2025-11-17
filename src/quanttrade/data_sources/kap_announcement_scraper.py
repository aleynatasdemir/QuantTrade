import requests
import json
import csv
from pathlib import Path

BASE_URL = "https://www.kap.org.tr"

# Output klasörünü ayarla
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "announcements"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
        "disclosureClass": "",
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
            "summary": item.get("summary"),
            "url": f"https://www.kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}"
        })

    return results


# ---- KULLANIM ----
ACSEL_OID = "4028e4a2420327a4014209c55161144d"

reports = fetch_financial_reports("2024-01-01", "2024-12-31", ACSEL_OID)

print(f"✓ Bulunan finansal rapor: {len(reports)}")

# CSV olarak kaydet
if reports:
    csv_file = OUTPUT_DIR / "acsel_finansal_raporlar.csv"
    
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "publishDate", "summary", "url"])
        writer.writeheader()
        writer.writerows(reports)
    
    print(f"✓ CSV kaydedildi: {csv_file}")
else:
    print("❌ Hiç rapor bulunamadı")
