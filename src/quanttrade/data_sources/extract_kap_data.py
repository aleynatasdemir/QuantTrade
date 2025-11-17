#!/usr/bin/env python3
"""
Parse symbols from names.txt and map to KAP company OIDs
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
import tomllib

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.toml"
NAMES_FILE = Path(__file__).parent.parent / "names.txt"
OUTPUT_DIR = PROJECT_ROOT / "data" / "kap"


def load_config() -> Dict:
    """Load configuration from TOML file."""
    try:
        with open(CONFIG_PATH, "rb") as f:
            config = tomllib.load(f)
        return config
    except Exception as e:
        print(f"ERROR loading config: {e}")
        return {}


def extract_symbols_and_companies(file_path: Path) -> tuple[List[str], List[Dict], str]:
    """
    Extract both the symbol list AND company JSON from the HTML names.txt file.
    
    Returns: (symbols_list, companies_list, raw_content)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"✓ Read {file_path.name}")
        
        # Step 1: Extract symbol list after "stockCode"
        symbols = []
        if "stockCode" in content:
            idx = content.find("stockCode")
            # After "stockCode" marker, symbols are listed one per line in uppercase
            symbol_section = content[idx:]
            
            # Find uppercase symbols (2-6 character stock codes)
            pattern_symbols = re.findall(r'\n([A-Z]{2,6})\n', symbol_section)
            
            if pattern_symbols:
                # Remove duplicates while preserving order
                seen = set()
                symbols = []
                for sym in pattern_symbols:
                    if sym not in seen:
                        symbols.append(sym)
                        seen.add(sym)
        
        print(f"✓ Extracted {len(symbols)} stock symbols from symbol list")
        
        # Step 2: Extract company JSON
        companies = []
        if "[{" in content:
            # Find the JSON array
            array_start = content.find("[{")
            if array_start > 0:
                # Find matching ]
                bracket_count = 1
                pos = array_start + 1
                while pos < len(content) and bracket_count > 0:
                    if content[pos] == '[':
                        bracket_count += 1
                    elif content[pos] == ']':
                        bracket_count -= 1
                    pos += 1
                
                json_str = content[array_start:pos]
                
                # Unescape JSON
                json_str = json_str.replace('\\"', '"')
                
                try:
                    companies = json.loads(json_str)
                    print(f"✓ Extracted {len(companies)} company records from JSON")
                except json.JSONDecodeError as e:
                    print(f"⚠ Warning: Could not parse JSON: {e}")
        
        return symbols, companies, content
        
    except Exception as e:
        print(f"ERROR: {e}")
        return [], [], ""


def match_symbols_to_companies(
    symbols: List[str],
    companies: List[Dict]
) -> Dict[str, Dict]:
    """
    Match stock symbols to company OID data.
    
    Company JSON might have different field names, so try multiple:
    - stockCode, kapMemberTitle, mkkMemberOid (from KAP API)
    - title, kapMemberTitle, relatedMemberTitle (variations)
    """
    print("\n🔍 Matching symbols to company OIDs...")
    
    matched = {}
    
    # Create lookup by various possible fields
    by_code = {}
    by_title = {}
    
    for company in companies:
        # Try to find stock code field
        stock_code = None
        for code_field in ['stockCode', 'symbol', 'code']:
            if code_field in company:
                stock_code = company[code_field]
                break
        
        if stock_code:
            code_upper = stock_code.upper().strip()
            by_code[code_upper] = company
        
        # Try to find title field
        title = None
        for title_field in ['kapMemberTitle', 'title', 'relatedMemberTitle', 'name']:
            if title_field in company:
                title = company[title_field]
                break
        
        if title:
            title_upper = title.upper().strip()
            by_title[title_upper] = company
    
    # Match each symbol
    for symbol in symbols:
        symbol_upper = symbol.upper().strip()
        
        if symbol_upper in by_code:
            company = by_code[symbol_upper]
            matched[symbol_upper] = {
                "title": company.get("kapMemberTitle", company.get("title", "")),
                "oid": company.get("mkkMemberOid", ""),
                "member_type": company.get("kapMemberType", company.get("memberType", "")),
                "city": company.get("cityName", "")
            }
    
    print(f"✓ Matched {len(matched)}/{len(symbols)} symbols ({(len(matched)/len(symbols)*100):.1f}%)")
    
    if len(matched) < len(symbols):
        unmatched = set(symbols) - set(matched.keys())
        print(f"\n⚠ {len(unmatched)} symbols could not be matched:")
        for sym in sorted(unmatched)[:10]:
            print(f"  - {sym}")
        if len(unmatched) > 10:
            print(f"  ... and {len(unmatched) - 10} more")
    
    return matched


def save_results(
    symbols: List[str],
    matched: Dict[str, Dict],
    output_dir: Path
) -> Optional[Path]:
    """Save results to files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save OID mapping
    mapping_file = output_dir / "bist_symbols_oids.json"
    output_data = {
        "metadata": {
            "source": "KAP (Kamuyu Aydınlatma Platformu) - parsed from names.txt",
            "total_symbols": len(symbols),
            "matched": len(matched)
        },
        "companies": matched
    }
    
    try:
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved OID mapping to {mapping_file}")
    except Exception as e:
        print(f"ERROR saving mapping: {e}")
        return None
    
    # Save symbol list
    symbols_file = output_dir / "all_bist_symbols.txt"
    try:
        with open(symbols_file, "w", encoding="utf-8") as f:
            f.write("\n".join(symbols))
        print(f"✓ Saved symbol list ({len(symbols)} symbols) to {symbols_file}")
    except Exception as e:
        print(f"ERROR saving symbols: {e}")
    
    return mapping_file


def main():
    """Main execution."""
    print("=" * 70)
    print("PARSE KAP COMPANY DATA FROM names.txt")
    print("=" * 70 + "\n")
    
    # Extract symbols and companies from names.txt
    symbols, companies, raw_content = extract_symbols_and_companies(NAMES_FILE)
    
    if not symbols:
        print("ERROR: No symbols found in names.txt")
        sys.exit(1)
    
    if not companies:
        print("ERROR: No company data found in names.txt")
        sys.exit(1)
    
    # Match symbols to companies
    matched = match_symbols_to_companies(symbols, companies)
    
    # Save results
    save_results(symbols, matched, OUTPUT_DIR)
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total symbols found:        {len(symbols)}")
    print(f"Total company records:      {len(companies)}")
    print(f"Successfully matched:       {len(matched)}")
    print(f"Match rate:                 {(len(matched)/len(symbols)*100):.1f}%")
    
    if matched:
        print("\nSample matched companies:")
        for i, (sym, data) in enumerate(list(matched.items())[:5], 1):
            print(f"  {i}. {sym:8s} → {data['title'][:45]}")
            print(f"     OID: {data['oid']}")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
