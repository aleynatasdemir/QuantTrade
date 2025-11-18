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


if __name__ == "__main__":
    print("=" * 70)
    print("TEMETTÜ SCRAPER")
    print("=" * 70)
    
    # Config'ten semboller ve tarih aralığı
    print("\n📋 Semboller ve tarih aralığı yükleniyor...")
    symbols = get_stock_symbols()
    start_date, end_date = get_stock_date_range()
    
    print(f"   ✓ {len(symbols)} sembol yüklendi")
    print(f"   ✓ Tarih aralığı: {start_date} - {end_date}")
    
    # Her sembol için temettü çek
    print("\n🔍 Temettüler çekiliyor...\n")
    
    success_count = 0
    fail_count = 0
    
    for symbol in symbols:
        print(f"   {symbol}...", end=" ", flush=True)
        
        try:
            df = scrape_dividends(symbol)
            
            if not df.empty:
                # Tarih aralığına göre filtrele
                df_filtered = filter_by_date_range(df, start_date, end_date)
                
                if not df_filtered.empty:
                    csv_file = OUTPUT_DIR / f"{symbol}_dividends.csv"
                    df_filtered.to_csv(csv_file, index=False, encoding="utf-8-sig")
                    
                    print(f"✓ {len(df_filtered)}/{len(df)} kayıt (filtrelenmiş)")
                    success_count += 1
                else:
                    print(f"⚠ Tarih aralığında veri yok ({len(df)} toplam)")
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
    print(f"Başarılı: {success_count}")
    print(f"Başarısız/Boş: {fail_count}")
    print(f"Tarih aralığı: {start_date} - {end_date}")
    print(f"Klasör: {OUTPUT_DIR}")
    print("=" * 70)
