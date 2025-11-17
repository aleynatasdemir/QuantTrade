#!/usr/bin/env python3
"""
KAP Companies Parser
Parses KAP company JSON data from names.txt and matches with stock symbols
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set

# Paths
PROJECT_ROOT = Path(__file__).parent
INPUT_FILE = PROJECT_ROOT / "names.txt"
OUTPUT_FILE = PROJECT_ROOT / "kap_symbols_oids_mapping.json"

# Load stock symbols from config
from src.quanttrade.config import get_stock_symbols

def parse_kap_json_from_text(text: str) -> List[Dict]:
    """
    Parse KAP company JSON objects from text content.
    Extracts mkkMemberOid, kapMemberTitle, stockCode from JSON structures.
    """
    results = []
    
    # Find all JSON objects in the text - match balanced braces
    # This regex finds {...} patterns with JSON content
    pattern = r'\{[^{}]*?"mkkMemberOid"[^{}]*?"kapMemberTitle"[^{}]*?"stockCode"[^{}]*?\}'
    
    matches = re.finditer(pattern, text, re.DOTALL)
    
    for match in matches:
        json_str = match.group(0)
        
        try:
            # Try to parse as JSON
            obj = json.loads(json_str)
            
            mkkMemberOid = obj.get("mkkMemberOid", "").strip()
            kapMemberTitle = obj.get("kapMemberTitle", "").strip()
            stockCode = obj.get("stockCode", "").strip()
            kapMemberOid = obj.get("kapMemberOid", "").strip()
            permaLink = obj.get("permaLink", "").strip()
            
            if mkkMemberOid and kapMemberTitle and stockCode:
                results.append({
                    "mkkMemberOid": mkkMemberOid,
                    "kapMemberTitle": kapMemberTitle,
                    "stockCode": stockCode.upper(),
                    "kapMemberOid": kapMemberOid,
                    "permaLink": permaLink
                })
        except json.JSONDecodeError:
            # If JSON parsing fails, try regex extraction
            oid_match = re.search(r'"mkkMemberOid"\s*:\s*"([^"]*)"', json_str)
            title_match = re.search(r'"kapMemberTitle"\s*:\s*"([^"]*)"', json_str)
            stock_match = re.search(r'"stockCode"\s*:\s*"([^"]*)"', json_str)
            
            if oid_match and title_match and stock_match:
                oid = oid_match.group(1).strip()
                title = title_match.group(1).strip()
                code = stock_match.group(1).strip().upper()
                
                if oid and title and code:
                    results.append({
                        "mkkMemberOid": oid,
                        "kapMemberTitle": title,
                        "stockCode": code,
                        "kapMemberOid": "",
                        "permaLink": ""
                    })
    
    return results


def match_with_symbols(companies: List[Dict], config_symbols: Set[str]) -> Dict[str, Dict]:
    """
    Match KAP companies with stock symbols from config.
    Returns: {symbol: {title, oid, ...}}
    """
    matched = {}
    
    for company in companies:
        stock_code = company.get("stockCode", "").upper().strip()
        
        if stock_code in config_symbols:
            matched[stock_code] = {
                "title": company.get("kapMemberTitle"),
                "oid": company.get("mkkMemberOid"),
                "kapMemberOid": company.get("kapMemberOid", ""),
                "permaLink": company.get("permaLink", "")
            }
    
    return matched


def main():
    """Main execution"""
    print("=" * 70)
    print("KAP COMPANIES PARSER")
    print("=" * 70)
    
    # Check if names.txt exists
    if not INPUT_FILE.exists():
        print(f"❌ Dosya bulunamadı: {INPUT_FILE}")
        print(f"   Lütfen names.txt dosyasını kontrol edin.")
        return
    
    print(f"\n📖 Okunuyor: {INPUT_FILE}")
    
    # Read the file
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        # Try different encodings
        for encoding in ["utf-16", "cp1252", "latin-1"]:
            try:
                with open(INPUT_FILE, "r", encoding=encoding) as f:
                    text = f.read()
                print(f"   ✓ Dosya {encoding} ile okundu")
                break
            except:
                continue
    
    print(f"   Boyut: {len(text)} karakter")
    
    # Parse JSON objects
    print("\n🔍 JSON nesneleri ayrıştırılıyor...")
    companies = parse_kap_json_from_text(text)
    print(f"   ✓ {len(companies)} şirket bulundu")
    
    if len(companies) == 0:
        print("   ❌ Hiç şirket bulunamadı. Dosya formatı kontrol edin.")
        # Debug: print first 500 chars
        print(f"\n   Dosya başlangıcı (ilk 500 char):\n   {text[:500]}")
        return
    
    # Load config symbols
    print("\n📋 Config sembolları yükleniyor...")
    try:
        config_symbols = get_stock_symbols()
        print(f"   ✓ {len(config_symbols)} sembol yüklendi")
    except Exception as e:
        print(f"   ❌ Config hatası: {e}")
        return
    
    # Match symbols with companies
    print("\n🔗 Semboller eşleştiriliyor...")
    matched = match_with_symbols(companies, config_symbols)
    print(f"   ✓ {len(matched)} sembol eşleştirildi")
    print(f"   ❌ {len(config_symbols) - len(matched)} sembol bulunamadı")
    
    # Show unmatched symbols
    unmatched = config_symbols - set(matched.keys())
    if unmatched:
        print("\n   Bulunamayan semboller:")
        for sym in sorted(unmatched)[:10]:  # Show first 10
            print(f"   - {sym}")
        if len(unmatched) > 10:
            print(f"   ... ve {len(unmatched) - 10} daha")
    
    # Save results
    print(f"\n💾 Kaydediliyor: {OUTPUT_FILE}")
    
    output_data = {
        "metadata": {
            "source": "KAP (Kamuyu Aydınlatma Platformu)",
            "total_parsed": len(companies),
            "total_matched": len(matched),
            "match_rate": f"{(len(matched)/len(config_symbols)*100):.1f}%"
        },
        "companies": matched
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"   ✓ {OUTPUT_FILE} kaydedildi")
    
    # Print summary
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print(f"Ayrıştırılan şirketler: {len(companies)}")
    print(f"Config sembolları: {len(config_symbols)}")
    print(f"Eşleştirilen: {len(matched)}")
    print(f"Başarı oranı: {(len(matched)/len(config_symbols)*100):.1f}%")
    
    # Show sample
    if matched:
        print("\nÖrnekler (ilk 5):")
        for i, (sym, data) in enumerate(list(matched.items())[:5], 1):
            print(f"  {i}. {sym}: {data['title']}")
            print(f"     OID: {data['oid']}")
    
    print("=" * 70)
