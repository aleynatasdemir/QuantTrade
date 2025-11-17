#!/usr/bin/env python3
"""
KAP Data Parser - Extracts JSON from Next.js streamed response
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).parent
INPUT_FILE = PROJECT_ROOT / "names.txt"
OUTPUT_FILE = PROJECT_ROOT / "kap_symbols_oids_mapping.json"

def extract_companies_from_nextjs_response(text: str) -> List[Dict]:
    """
    Extract companies from Next.js self.__next_f.push([...]) format.
    The data is in escaped JSON within the script tag.
    """
    companies = []
    
    # The JSON is escaped with backslashes: \" instead of "
    # We need to search for the escaped version: \\"mkkMemberOid\\"
    
    # Find all positions of escaped mkkMemberOid
    oid_positions = [m.start() for m in re.finditer(r'mkkMemberOid', text)]
    
    print(f"   ℹ {len(oid_positions)} potential company records found")
    
    for oid_pos in oid_positions:
        # Go backwards to find the opening brace (escaped as \{ or just {)
        start_pos = oid_pos
        while start_pos > 0 and text[start_pos] not in ['{', '}']:
            start_pos -= 1
        
        if start_pos == 0 or text[start_pos] != '{':
            continue
        
        # Go forward from opening brace to find matching closing brace
        brace_count = 0
        pos = start_pos
        in_string = False
        escape_next = False
        
        while pos < len(text):
            char = text[pos]
            
            # Handle escape sequences
            if escape_next:
                escape_next = False
                pos += 1
                continue
            
            if char == '\\':
                escape_next = True
                pos += 1
                continue
            
            # Track if we're inside a string
            if char == '"':
                in_string = not in_string
            
            # Only count braces outside of strings
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the closing brace
                        obj_str = text[start_pos:pos+1]
                        
                        try:
                            # Unescape the string: \" -> "
                            obj_str = obj_str.replace('\\"', '"')
                            obj_str = obj_str.replace('\\/', '/')
                            
                            # Try to parse as JSON
                            obj = json.loads(obj_str)
                            
                            # Validate required fields
                            if (isinstance(obj, dict) and 
                                "mkkMemberOid" in obj and 
                                "kapMemberTitle" in obj and 
                                "stockCode" in obj):
                                
                                oid = obj.get("mkkMemberOid", "").strip()
                                title = obj.get("kapMemberTitle", "").strip()
                                stock_code_str = obj.get("stockCode", "").strip()
                                
                                # Handle multiple stock codes (e.g., "HALKB, THL" or "ISCTR, ISATR")
                                # Split by comma and take all codes
                                stock_codes = [code.strip().upper() for code in stock_code_str.split(",")]
                                
                                if oid and title and stock_codes:
                                    # Add an entry for each stock code
                                    for code in stock_codes:
                                        if code:  # Skip empty strings
                                            companies.append({
                                                "mkkMemberOid": oid,
                                                "kapMemberTitle": title,
                                                "stockCode": code
                                            })
                        except (json.JSONDecodeError, ValueError) as e:
                            # Not valid JSON, skip
                            pass
                        
                        break
            pos += 1
    
    return companies


def load_config_symbols() -> Set[str]:
    """Load symbols from config"""
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.quanttrade.config import get_stock_symbols
        
        symbols = get_stock_symbols()
        return set(s.upper() for s in symbols)
    except Exception as e:
        print(f"⚠ Config hatası: {e}")
        # Fallback from settings.toml
        return {
            "AKBNK", "GARAN", "ISCTR", "VAKBN", "YKBNK", "HALKB",
            "KCHOL", "SAHOL", "DOHOL", "THYAO",
            "ARCLK", "ASELS", "EREGL", "FROTO", "SISE", "TUPRS", "TOASO",
            "AKSEN", "ENKAI", "PETKM",
            "TTKOM", "TCELL", "LOGO",
            "MGROS", "SOKM", "BIMAS", "VESTL", "ULKER", "AEFES", "CCOLA",
            "EKGYO", "PGSUS", "TKFEN", "KONTR", "TTRAK",
            "KOZAL", "KOZAA", "KRDMD",
            "TAVHL"
        }


def main():
    print("=" * 70)
    print("KAP DATA PARSER")
    print("=" * 70)
    
    # Read input file
    print(f"\n📖 Okunuyor: {INPUT_FILE}")
    
    if not INPUT_FILE.exists():
        print(f"❌ Dosya bulunamadı: {INPUT_FILE}")
        return
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    
    print(f"   ✓ Dosya okundu ({len(text)} karakter)")
    
    # Extract companies
    print("\n🔍 Şirketler ayrıştırılıyor...")
    
    companies = extract_companies_from_nextjs_response(text)
    
    if not companies:
        print("   ❌ Hiç şirket bulunamadı!")
        # Debug
        print("\n   DEBUG: İlk 1000 karakter:")
        print("   " + text[:1000].replace("\n", "\n   "))
        return
    
    print(f"   ✓ {len(companies)} şirket bulundu")
    
    # Convert all companies to dictionary format (no filtering)
    print("\n🔗 Tüm şirketler dönüştürülüyor...")
    matched = {}
    
    for company in companies:
        code = company.get("stockCode", "").upper()
        if code:  # Only require non-empty code
            matched[code] = {
                "title": company.get("kapMemberTitle"),
                "oid": company.get("mkkMemberOid")
            }
    
    matched_count = len(matched)
    
    print(f"   ✓ {matched_count} sembol hazır")
    
    # Save results
    print(f"\n💾 Kaydediliyor: {OUTPUT_FILE}")
    
    output_data = {
        "metadata": {
            "source": "KAP (Kamuyu Aydınlatma Platformu)",
            "total_parsed": len(companies),
            "total_companies": matched_count,
            "extraction_date": "2025-11-17"
        },
        "companies": matched
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"   ✓ Kaydedildi")
    
    # Summary
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print(f"Ayrıştırılan şirketler: {len(companies)}")
    print(f"Toplam sembol: {matched_count}")
    
    # Show samples
    if matched:
        print("\nÖrnekler (ilk 10):")
        for i, (sym, data) in enumerate(list(matched.items())[:10], 1):
            print(f"  {i}. {sym}")
            print(f"     Başlık: {data['title'][:60]}...")
            print(f"     OID: {data['oid']}")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
