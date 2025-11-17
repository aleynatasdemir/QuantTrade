import requests
import json
import ssl
import time

# SSL verify kapat (KAP için gerekli)
ssl._create_default_https_context = ssl._create_unverified_context

BASE_URL = "https://www.kap.org.tr"

session = requests.Session()

# Stabil cookie alma
session.get(BASE_URL + "/tr/anasayfa", timeout=10)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/tr/bildirim-sorgu",
    "Connection": "keep-alive"
}

def fetch_financial_reports(from_date, to_date, oid):
    url = BASE_URL + "/tr/api/disclosure/members/byCriteria"

    payload = {
        "fromDate": from_date,
        "toDate": to_date,
        "members": [
            {"memberOid": oid, "memberType": "IGS"}
        ],
        "disclosureClass": ["FR"],
        "sort": {"field": "publishDate", "order": "desc"}
    }

    # Retry yap (KAP bazen reset atıyor)
    for _ in range(3):
        try:
            r = session.post(url, headers=headers, data=json.dumps(payload), timeout=15)
            data = r.json()
            break
        except Exception as e:
            print("Retry:", e)
            time.sleep(1)
    else:
        print("API hiç cevap vermedi")
        return []

    if not isinstance(data, list):
        print("API list döndürmedi →", type(data))
        print(data)
        return []

    results = []
    for item in data:

        # HATA BURADAYDI ⇒ string elemanları temizle
        if not isinstance(item, dict):
            continue

        subject = item.get("subject", "")

        if "Finansal" not in subject and "Rapor" not in subject:
            continue

        results.append({
            "index": item.get("disclosureIndex"),
            "publishDate": item.get("publishDate"),
            "summary": item.get("summary"),
            "url": f"https://www.kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}"
        })

    return results


ACSEL_OID = "4028e4a2420327a4014209c55161144d"

reports = fetch_financial_reports("01.01.2024", "31.12.2024", ACSEL_OID)

print("Bulunan finansal rapor:", len(reports))
print(json.dumps(reports, indent=2, ensure_ascii=False))
