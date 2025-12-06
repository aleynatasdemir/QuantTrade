"""
Temettü Scraper - INCREMENTAL MOD

INCREMENTAL LOGIC:
- Her sembol için mevcut CSV dosyasına bakar
- Son dağıtım tarihinden sonraki yeni temettüleri çeker
- Eski veriyle birleştirir, duplikatları temizler
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import time
from pathlib import Path

# Project root ve config
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "dividend"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
from src.quanttrade.config import get_stock_symbols, get_stock_date_range
from datetime import datetime


def scrape_dividends(symbol):
    """Bir sembol için tüm temettü verilerini çeker."""
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={symbol}"
    
    try:
        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        # Tüm temettü satırları
        rows = soup.select("tbody.temettugercekvarBody.hepsi tr.temettugercekvarrow")

        data = []
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cols) == 0:
                continue
            
            data.append({
                "Kod": cols[0] if len(cols) > 0 else "",
                "Dagitim_Tarihi": cols[1] if len(cols) > 1 else "",
                "Temettu_Verim": cols[2] if len(cols) > 2 else "",
                "Hisse_Basi_TL": cols[3] if len(cols) > 3 else "",
                "Brut_Oran": cols[4] if len(cols) > 4 else "",
                "Net_Oran": cols[5] if len(cols) > 5 else "",
                "Toplam_Temettu_TL": cols[6] if len(cols) > 6 else "",
                "Dagitma_Orani": cols[7] if len(cols) > 7 else ""
            })

        df = pd.DataFrame(data)
        return df
    except Exception as e:
        print(f"❌ Hata: {e}")
        return pd.DataFrame()


def filter_by_date_range(df, start_date, end_date):
    """Tarih aralığına göre filtrele"""
    if df.empty:
        return df
    
    try:
        # Tarihi parse et (format: DD.MM.YYYY)
        df['Dagitim_Tarihi_Parsed'] = pd.to_datetime(df['Dagitim_Tarihi'], format='%d.%m.%Y', errors='coerce')
        
        # Start ve end date'i datetime'a çevir
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Filtrele
        mask = (df['Dagitim_Tarihi_Parsed'] >= start_dt) & (df['Dagitim_Tarihi_Parsed'] <= end_dt)
        filtered_df = df[mask].copy()
        
        # Geçici kolonu sil
        filtered_df = filtered_df.drop('Dagitim_Tarihi_Parsed', axis=1)
        
        return filtered_df
    except Exception as e:
        print(f"⚠ Tarih filtreleme hatası: {e}")
        return df


def get_last_dividend_date(file_path):
    """Mevcut dosyadaki son temettü tarihini döndürür."""
    if not file_path.exists():
        return None
    
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        if df.empty or 'Dagitim_Tarihi' not in df.columns:
            return None
        
        # Tarihleri parse et
        df['Dagitim_Tarihi_Parsed'] = pd.to_datetime(df['Dagitim_Tarihi'], format='%d.%m.%Y', errors='coerce')
        df = df[df['Dagitim_Tarihi_Parsed'].notna()]
        
        if df.empty:
            return None
        
        return df['Dagitim_Tarihi_Parsed'].max()
    except Exception as e:
        print(f"⚠ Dosya okuma hatası: {e}")
        return None


def merge_and_save_dividends(old_df, new_df, file_path):
    """Eski ve yeni temettü verilerini birleştirir ve kaydeder."""
    if old_df.empty and new_df.empty:
        return 0
    
    if old_df.empty:
        combined = new_df
    elif new_df.empty:
        combined = old_df
    else:
        combined = pd.concat([old_df, new_df], ignore_index=True)
    
    # Duplikatları temizle (Kod + Dagitim_Tarihi üzerinden)
    combined = combined.drop_duplicates(subset=['Kod', 'Dagitim_Tarihi'], keep='last')
    
    # Tarihe göre sırala (en yeni en üstte)
    try:
        combined['_sort_date'] = pd.to_datetime(combined['Dagitim_Tarihi'], format='%d.%m.%Y', errors='coerce')
        combined = combined.sort_values('_sort_date', ascending=False)
        combined = combined.drop('_sort_date', axis=1)
    except:
        pass
    
    combined = combined.reset_index(drop=True)
    combined.to_csv(file_path, index=False, encoding="utf-8-sig")
    
    return len(combined)


if __name__ == "__main__":
    print("=" * 70)
    print("TEMETTÜ SCRAPER (INCREMENTAL MOD)")
    print("=" * 70)
    
    # Config'ten semboller ve tarih aralığı
    print("\n📋 Semboller ve tarih aralığı yükleniyor...")
    symbols = get_stock_symbols()
    start_date, end_date = get_stock_date_range()
    
    print(f"   ✓ {len(symbols)} sembol yüklendi")
    print(f"   ✓ Config tarih aralığı: {start_date} - {end_date}")
    print("\n   NOT: Her sembol için mevcut veri kontrol edilecek.")
    print("        Sadece yeni temettüler çekilecek.")
    
    # Her sembol için temettü çek
    print("\n🔍 Temettüler çekiliyor...\n")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for symbol in symbols:
        csv_file = OUTPUT_DIR / f"{symbol}_dividends.csv"
        
        # Mevcut dosyadaki son tarihi kontrol et
        last_date = get_last_dividend_date(csv_file)
        
        print(f"   {symbol}...", end=" ", flush=True)
        
        try:
            # Tüm temettüleri çek (site zaten tüm geçmişi veriyor)
            df = scrape_dividends(symbol)
            
            if not df.empty:
                # Tarih aralığına göre filtrele
                df_filtered = filter_by_date_range(df, start_date, end_date)
                
                if df_filtered.empty:
                    print(f"⚠ Tarih aralığında veri yok")
                    fail_count += 1
                    time.sleep(1)
                    continue
                
                # Eğer mevcut veri varsa ve yeni veri yoksa atla
                if last_date is not None:
                    df_filtered['_check_date'] = pd.to_datetime(df_filtered['Dagitim_Tarihi'], format='%d.%m.%Y', errors='coerce')
                    new_records = df_filtered[df_filtered['_check_date'] > last_date]
                    df_filtered = df_filtered.drop('_check_date', axis=1)
                    
                    if new_records.empty:
                        print(f"✓ Güncel (son: {last_date.strftime('%d.%m.%Y')})")
                        skip_count += 1
                        time.sleep(0.5)
                        continue
                
                # Mevcut veriyi oku
                old_df = pd.DataFrame()
                if csv_file.exists():
                    try:
                        old_df = pd.read_csv(csv_file, encoding='utf-8-sig')
                    except:
                        old_df = pd.DataFrame()
                
                # Birleştir ve kaydet
                total_count = merge_and_save_dividends(old_df, df_filtered, csv_file)
                
                if last_date:
                    print(f"✓ Güncellendi ({total_count} toplam)")
                else:
                    print(f"✓ {total_count} kayıt")
                success_count += 1
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
