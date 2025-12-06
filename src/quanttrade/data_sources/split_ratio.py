"""
Split Ratio Scraper - INCREMENTAL MOD

INCREMENTAL LOGIC:
- Her sembol için mevcut CSV dosyasına bakar
- Son split tarihinden sonraki yeni bölünmeleri çeker
- Eski veriyle birleştirir, duplikatları temizler
"""

import requests
import pandas as pd
import json
import sys
import time
from pathlib import Path
from io import StringIO

# Project root ve config
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "split_ratio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols, get_stock_date_range
from datetime import datetime

URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/GetSermayeArttirimlari"


def get_split_data(symbol):
    """Bir sembol için tüm split verilerini çeker."""
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.isyatirim.com.tr",
        "Referer": f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}",
        "Connection": "keep-alive",
    }

    payload = {
        "hisseKodu": symbol,
        "hisseTanimKodu": "",
        "yil": 0,
        "zaman": "HEPSI",
        "endeksKodu": "09",
        "sektorKodu": ""
    }

    try:
        r = session.post(URL, headers=headers, data=json.dumps(payload), timeout=10, verify=True)
        r.raise_for_status()

        raw_json = r.json()["d"]
        
        df = pd.read_json(StringIO(raw_json))

        # Split oranı hesaplama
        if not df.empty and "HSP_BOLUNME_ONCESI_SERMAYE" in df.columns and "HSP_BOLUNME_SONRASI_SERMAYE" in df.columns:
            df["SPLIT_RATIO"] = df["HSP_BOLUNME_SONRASI_SERMAYE"] / df["HSP_BOLUNME_ONCESI_SERMAYE"]

        return df
    except Exception as e:
        print(f"❌ Hata: {e}")
        return pd.DataFrame()


def filter_by_date_range(df, start_date, end_date):
    """Tarih aralığına göre filtrele"""
    if df.empty:
        return df
    
    try:
        # Tarih kolonu: SHHE_TARIH
        if 'SHHE_TARIH' not in df.columns:
            return df
        
        # Tarihi timestamp'den datetime'a çevir (milliseconds)
        df['SHHE_TARIH'] = pd.to_datetime(df['SHHE_TARIH'], unit='ms', errors='coerce')
        
        # Start ve end date'i datetime'a çevir
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Filtrele
        mask = (df['SHHE_TARIH'] >= start_dt) & (df['SHHE_TARIH'] <= end_dt)
        filtered_df = df[mask].copy()
        
        return filtered_df
    except Exception as e:
        print(f"⚠ Tarih filtreleme hatası: {e}")
        return df


def get_last_split_date(file_path):
    """Mevcut dosyadaki son split tarihini döndürür."""
    if not file_path.exists():
        return None
    
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        if df.empty or 'SHHE_TARIH' not in df.columns:
            return None
        
        # Tarihleri parse et
        df['SHHE_TARIH'] = pd.to_datetime(df['SHHE_TARIH'], errors='coerce')
        df = df[df['SHHE_TARIH'].notna()]
        
        if df.empty:
            return None
        
        return df['SHHE_TARIH'].max()
    except Exception as e:
        print(f"⚠ Dosya okuma hatası: {e}")
        return None


def merge_and_save_splits(old_df, new_df, file_path):
    """Eski ve yeni split verilerini birleştirir ve kaydeder."""
    if old_df.empty and new_df.empty:
        return 0
    
    if old_df.empty:
        combined = new_df
    elif new_df.empty:
        combined = old_df
    else:
        combined = pd.concat([old_df, new_df], ignore_index=True)
    
    # Duplikatları temizle (SHHE_TARIH üzerinden - her tarihte tek split olabilir)
    if 'SHHE_TARIH' in combined.columns:
        combined = combined.drop_duplicates(subset=['SHHE_TARIH'], keep='last')
        
        # Tarihe göre sırala
        combined = combined.sort_values('SHHE_TARIH', ascending=False)
    
    combined = combined.reset_index(drop=True)
    combined.to_csv(file_path, index=False, encoding="utf-8-sig")
    
    return len(combined)


if __name__ == "__main__":
    print("=" * 70)
    print("SPLIT RATIO SCRAPER (INCREMENTAL MOD)")
    print("=" * 70)
    
    # Config'ten semboller ve tarih aralığı
    print("\n📋 Semboller ve tarih aralığı yükleniyor...")
    symbols = get_stock_symbols()
    start_date, end_date = get_stock_date_range()
    
    print(f"   ✓ {len(symbols)} sembol yüklendi")
    print(f"   ✓ Config tarih aralığı: {start_date} - {end_date}")
    print("\n   NOT: Her sembol için mevcut veri kontrol edilecek.")
    print("        Sadece yeni split'ler eklenecek.")
    
    # Her sembol için split ratio çek
    print("\n🔍 Split ratio verileri çekiliyor...\n")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for symbol in symbols:
        csv_file = OUTPUT_DIR / f"{symbol}_split.csv"
        
        # Mevcut dosyadaki son tarihi kontrol et
        last_date = get_last_split_date(csv_file)
        
        print(f"   {symbol}...", end=" ", flush=True)
        
        try:
            df = get_split_data(symbol)
            
            if not df.empty:
                # Tarih aralığına göre filtrele
                df_filtered = filter_by_date_range(df, start_date, end_date)
                
                # Mevcut veri varsa ve yeni veri yoksa atla
                if last_date is not None and not df_filtered.empty:
                    new_records = df_filtered[df_filtered['SHHE_TARIH'] > last_date]
                    
                    if new_records.empty:
                        print(f"✓ Güncel (son: {last_date.strftime('%Y-%m-%d')})")
                        skip_count += 1
                        time.sleep(0.5)
                        continue
                
                # Mevcut veriyi oku
                old_df = pd.DataFrame()
                if csv_file.exists():
                    try:
                        old_df = pd.read_csv(csv_file, encoding='utf-8-sig')
                        # Tarih kolonunu datetime'a çevir
                        if 'SHHE_TARIH' in old_df.columns:
                            old_df['SHHE_TARIH'] = pd.to_datetime(old_df['SHHE_TARIH'], errors='coerce')
                    except:
                        old_df = pd.DataFrame()
                
                # Yeni veri varsa birleştir
                if not df_filtered.empty:
                    total_count = merge_and_save_splits(old_df, df_filtered, csv_file)
                    
                    if last_date:
                        print(f"✓ Güncellendi ({total_count} toplam)")
                    else:
                        print(f"✓ {total_count} kayıt")
                    success_count += 1
                elif not old_df.empty:
                    # Tarih aralığında veri yok ama mevcut veri var
                    print(f"✓ Güncel ({len(old_df)} kayıt)")
                    skip_count += 1
                else:
                    print("⚠ Tarih aralığında veri yok")
                    fail_count += 1
            else:
                print("⚠ Veri yok")
                fail_count += 1
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Hata: {e}")
            fail_count += 1
            time.sleep(2)
    
    # Özet
    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    print(f"Toplam sembol: {len(symbols)}")
    print(f"Başarılı (yeni/güncelleme): {success_count}")
    print(f"Atlanan (güncel): {skip_count}")
    print(f"Başarısız/Boş: {fail_count}")
    print(f"Tarih aralığı: {start_date} - {end_date}")
    print(f"Klasör: {OUTPUT_DIR}")
    print("=" * 70)
