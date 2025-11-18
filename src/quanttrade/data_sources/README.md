# BIST Veri Toplama Sistemleri

Bu dizin BIST hisseleri için merkezi veri toplama sistemlerini içerir. Tüm sistemler `config/settings.toml` dosyasından hisse sembolleri ve tarih aralığı okur.

## 📋 Config Ayarları

`config/settings.toml` dosyasında `[stocks]` bölümünü düzenleyin:

```toml
[stocks]
# BIST hisse senetleri listesi
start_date = "2020-01-01"
end_date = "2025-11-17"

symbols = [
    "AKBNK", "GARAN", "ISCTR", "THYAO", "ASELS",
    # ... daha fazla sembol
]
```

## 🔧 Veri Toplama Sistemleri

### 1. BIST Data Collector (Finansal Veriler)
**Dosya:** `bist_data_collector.py`

**Ne yapar:**
- Her hisse için finansal tablo verilerini çeker (bilanço + gelir tablosu)
- Fiyat verilerini ve getiri hesaplamalarını yapar
- Tek bir CSV dosyasına tüm verileri birleştirir

**Çıktı veriler:**
- `ticker`: Hisse kodu
- `period`: Finansal dönem (örn: 2025/9)
- `net_profit`: Net dönem karı
- `sales`: Net satışlar (bankalar için NaN olabilir)
- `total_debt`: Toplam borç
- `total_equity`: Özkaynak
- `return_1y`: 1 yıllık getiri (%)
- `return_3y`: 3 yıllık getiri (%)
- `return_5y`: 5 yıllık getiri (%)
- `current_price`: Güncel fiyat

**Kullanım:**
```bash
cd src/quanttrade/data_sources
python bist_data_collector.py
```

**Çıktı:**
```
data/raw/stocks/bist_isyatirimhisse_full_dataset.csv
```

### 2. İş Yatırım OHLCV Downloader (Fiyat Verileri)
**Dosyalar:** `isyatirim_ohlcv.py` + `isyatirim_ohlcv_downloader.py`

**Ne yapar:**
- Her hisse için günlük OHLCV (Open, High, Low, Close, Volume) verilerini çeker
- Her hisse için ayrı CSV dosyası oluşturur
- Standart OHLCV formatında kaydeder

**Çıktı veriler (her hisse için):**
- `date`: Tarih (index)
- `open`: Açılış fiyatı
- `high`: En yüksek fiyat
- `low`: En düşük fiyat
- `close`: Kapanış fiyatı
- `volume`: İşlem hacmi
- `symbol`: Hisse kodu

**Kullanım:**
```bash
cd src/quanttrade/data_sources
python isyatirim_ohlcv_downloader.py
```

**Çıktı:**
```
data/raw/ohlcv/AKBNK_ohlcv_isyatirim.csv
data/raw/ohlcv/GARAN_ohlcv_isyatirim.csv
data/raw/ohlcv/THYAO_ohlcv_isyatirim.csv
...
```

## 📊 Veri Akış Diyagramı

```
config/settings.toml
    └─> [stocks] bölümü
         ├─> symbols (hisse listesi)
         ├─> start_date
         └─> end_date
              │
              ├─> bist_data_collector.py
              │    └─> isyatirimhisse API (finansal + fiyat)
              │         └─> data/raw/stocks/bist_isyatirimhisse_full_dataset.csv
              │
              └─> isyatirim_ohlcv_downloader.py
                   └─> isyatirimhisse API (OHLCV)
                        └─> data/raw/ohlcv/{SYMBOL}_ohlcv_isyatirim.csv
```

## 🎯 Hisse Listesi Güncelleme

### Config'den tüm hisseler için çalıştırma:
```python
# Her iki sistem de otomatik olarak config'den okur
python bist_data_collector.py          # Finansal veriler
python isyatirim_ohlcv_downloader.py   # OHLCV verileri
```

### Manuel hisse listesi ile çalıştırma:
```python
from bist_data_collector import BISTDataCollector

# Sadece belirli hisseler için
collector = BISTDataCollector(symbols=['AKBNK', 'GARAN', 'THYAO'])
collector.run(output_file='custom_dataset.csv')
```

```python
from isyatirim_ohlcv import fetch_ohlcv_from_isyatirim

# Sadece belirli hisseler için
fetch_ohlcv_from_isyatirim(
    symbols=['AKBNK', 'GARAN', 'THYAO'],
    start_date='2023-01-01',
    end_date='2025-11-17',
    output_dir='data/raw/ohlcv'
)
```

## ⚙️ Rate Limiting

Her iki sistem de API'yi yormamak için bekleme süreleri kullanır:
- **bist_data_collector.py**: Her hisse için 2 saniye bekler
- **isyatirim_ohlcv_downloader.py**: Her hisse için 0.5 saniye bekler

İhtiyaca göre bu değerleri kodda değiştirebilirsiniz.

## 📝 Log Dosyaları

Her iki sistem de detaylı log tutar:
- **bist_data_collector.log**: Finansal veri toplama logları
- Konsol çıktısı: Real-time ilerleme ve hata raporları

## 🔍 Hata Durumları

Sistemler hata durumlarında:
- ❌ Hata veren hisseyi atlar ve devam eder
- ✅ Başarılı hisseleri kaydeder
- 📊 Sonunda özet rapor verir

## 📦 Gereksinimler

```bash
pip install isyatirimhisse pandas numpy toml
```

## 💡 Örnek Kullanım Senaryosu

1. **Config'i güncelle:**
```toml
[stocks]
symbols = ["AKBNK", "GARAN", "THYAO", "ASELS", "TUPRS"]
start_date = "2023-01-01"
end_date = "2025-11-17"
```

2. **Finansal verileri çek:**
```bash
python bist_data_collector.py
# ✓ 5 hisse için finansal veriler toplandı
```

3. **OHLCV verilerini çek:**
```bash
python isyatirim_ohlcv_downloader.py
# ✓ 5 CSV dosyası oluşturuldu
```

4. **Verileri kullan:**
```python
import pandas as pd

# Finansal veriler
df_financials = pd.read_csv('data/raw/stocks/bist_isyatirimhisse_full_dataset.csv')

# Bir hissenin OHLCV verileri
df_ohlcv = pd.read_csv('data/raw/ohlcv/AKBNK_ohlcv_isyatirim.csv', index_col='date', parse_dates=True)
```

## 🎓 İleri Seviye

### Paralel Veri Çekimi
Daha hızlı veri toplamak için `concurrent.futures` kullanabilirsiniz:

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_parallel(symbols, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(fetch_single_stock, symbols)
```

### Incremental Update
Sadece yeni verileri çekmek için:

```python
# Son veri tarihini bul
last_date = df_ohlcv.index.max()

# Sadece yeni verileri çek
fetch_ohlcv_from_isyatirim(
    symbols=['AKBNK'],
    start_date=last_date.strftime('%Y-%m-%d'),
    end_date='2025-11-17'
)
```

---

**Son güncelleme:** 17 Kasım 2025
