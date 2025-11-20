# 📊 QuantTrade - Tam Veri Pipeline Rehberi

Bu dokümantasyon, sıfırdan master_df.csv'ye kadar tüm adımları açıklar.

## 🎯 Pipeline Adımları Özeti

```
1. DATA SOURCES      → Ham veri toplama (EVDS, Yahoo, KAP)
2. DATA PROCESSING   → Veri temizleme ve normalizasyon
3. FEATURE ENGINEERING → Feature üretimi ve master_df oluşturma
4. MODEL TRAINING    → ML model eğitimi
5. PREDICTION        → Tahmin ve sinyal üretimi
6. BACKTEST          → Performans değerlendirme
```

---

## 📥 ADIM 1: DATA SOURCES (Veri Toplama)

### 1.1. Makro Ekonomik Veriler (EVDS)

**Script:** `src/quanttrade/data_sources/macro_downloader.py`

```bash
cd /Users/furkanyilmaz/Desktop/QuantTrade
python3 src/quanttrade/data_sources/macro_downloader.py
```

**Ne Yapar?**
- TCMB EVDS API'den makro verileri çeker
- USD/TRY, EUR/TRY, BIST100, CPI, M2 vb.
- Çıktı: `data/raw/macro/evds_macro_daily.csv`

**Gereksinimler:**
- `.env` dosyasında `EVDS_API_KEY` tanımlı olmalı
- `config/settings.toml` ayarları kontrol et

---

### 1.2. Hisse Senedi Fiyat Verileri (OHLCV)

**Script:** `src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py`

```bash
python3 src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py
```

**Ne Yapar?**
- İş Yatırım API'den hisse senedi fiyatlarını çeker
- Open, High, Low, Close, Volume, Adjusted Close
- Çıktı: `data/raw/ohlcv/[SYMBOL]_ohlcv.csv` (her hisse için ayrı)

**Config:**
- `config/settings.toml` içinde `symbols` listesi
- Tarih aralığı: `start_date` ve `end_date`

---

### 1.3. Mali Tablo Verileri

**Script:** `src/quanttrade/data_sources/mali_tablo.py`

```bash
python3 src/quanttrade/data_sources/mali_tablo.py
```

**Ne Yapar?**
- İş Yatırım'dan mali tablo verilerini çeker
- Bilanço, Gelir Tablosu, Nakit Akışı
- Çıktı: `data/raw/mali_tablo/[SYMBOL]_financials.csv`

---

### 1.4. Temettü Verileri

**Script:** `src/quanttrade/data_sources/temettü_scraper.py`

```bash
python3 src/quanttrade/data_sources/temettü_scraper.py
```

**Ne Yapar?**
- KAP'tan temettü duyurularını çeker
- Çıktı: `data/raw/dividend/kap_temettü.csv`

---

### 1.5. Split Ratio Verileri

**Script:** `src/quanttrade/data_sources/split_ratio.py`

```bash
python3 src/quanttrade/data_sources/split_ratio.py
```

**Ne Yapar?**
- KAP'tan bedelsiz hisse ve split bilgilerini çeker
- Çıktı: `data/raw/split_ratio/kap_splits.csv`

---

### 1.6. KAP Duyuruları

**Script:** `src/quanttrade/data_sources/kap_announcement_scraper.py`

```bash
python3 src/quanttrade/data_sources/kap_announcement_scraper.py
```

**Ne Yapar?**
- KAP'tan önemli duyuruları çeker (birleşme, devralma vb.)
- Çıktı: `data/raw/announcements/kap_announcements.csv`

---

## 🧹 ADIM 2: DATA PROCESSING (Veri Temizleme)

### 2.1. OHLCV Temizleme

**Script:** `src/quanttrade/data_processing/ohlcv_cleaner.py`

```bash
cd /Users/furkanyilmaz/Desktop/QuantTrade
python3 src/quanttrade/data_processing/ohlcv_cleaner.py
```

**Ne Yapar?**
- Raw OHLCV dosyalarını okur
- NaN değerleri temizler
- Outlier'ları düzeltir
- Split/dividend adjustment kontrol eder
- Çıktı: `data/processed/ohlcv/[SYMBOL]_clean_ohlcv.csv`

**Log:** `src/quanttrade/data_processing/ohlcv_cleaner.log`

---

### 2.2. Mali Tablo Normalizasyonu

**Script:** `src/quanttrade/data_processing/mali_tablo_normalizer.py`

```bash
python3 src/quanttrade/data_processing/mali_tablo_normalizer.py
```

**Ne Yapar?**
- Raw mali tablo verilerini standardize eder
- Dönemsel/kümülatif ayırımı yapar
- Missing value handling
- Çıktı: `data/processed/mali_tablo/[SYMBOL]_normalized_financials.csv`

**Log:** `src/quanttrade/data_processing/mali_tablo_normalizer.log`

---

### 2.3. Makro Veri Temizleme

**Script:** `src/quanttrade/data_processing/macro_cleaner.py`

```bash
python3 src/quanttrade/data_processing/macro_cleaner.py
```

**Ne Yapar?**
- Makro verileri temizler ve resampling yapar
- Günlük, haftalık, aylık frekanslara çevirir
- Forward fill / interpolation
- Çıktı: `data/processed/macro/macro_clean.csv`

---

### 2.4. Split Verileri Temizleme

**Script:** `src/quanttrade/data_processing/split_cleaner.py`

```bash
python3 src/quanttrade/data_processing/split_cleaner.py
```

**Ne Yapar?**
- Split ratio verilerini temizler
- Tarih formatı düzeltme
- Çıktı: `data/processed/split/split_clean.csv`

**Log:** `src/quanttrade/data_processing/split_cleaner.log`

---

### 2.5. Temettü Verileri Temizleme

**Script:** `src/quanttrade/data_processing/dividend_cleaner.py`

```bash
python3 src/quanttrade/data_processing/dividend_cleaner.py
```

**Ne Yapar?**
- Temettü verilerini temizler
- Para birimi dönüşümleri
- Çıktı: `data/processed/dividend/dividend_clean.csv`

---

### 2.6. Duyuru Verileri Temizleme

**Script:** `src/quanttrade/data_processing/announcement_cleaner.py`

```bash
python3 src/quanttrade/data_processing/announcement_cleaner.py
```

**Ne Yapar?**
- KAP duyurularını kategorize eder
- Metin temizleme
- Çıktı: `data/processed/announcements/announcements_clean.csv`

---

## ⚙️ ADIM 3: FEATURE ENGINEERING

### 3.1. Fiyat Feature'ları

**Script:** `src/quanttrade/feature_engineering/price_feature_engineer.py`

```bash
cd /Users/furkanyilmaz/Desktop/QuantTrade
python3 src/quanttrade/feature_engineering/price_feature_engineer.py
```

**Ne Yapar?**
- Teknik indikatörler hesaplar:
  - RSI, MACD, Bollinger Bands
  - Moving averages (SMA, EMA)
  - Volatilite, ATR
  - Volume indicators
- Çıktı: `data/features/price/[SYMBOL]_price_features.csv`

**Log:** `src/quanttrade/feature_engineering/price_feature_engineer.log`

---

### 3.2. Fundamental Feature'lar

**Script:** `src/quanttrade/feature_engineering/fundamental_features.py`

```bash
python3 src/quanttrade/feature_engineering/fundamental_features.py
```

**Ne Yapar?**
- Mali tablolardan oranlar hesaplar:
  - ROE, ROA, ROI
  - Profit margins
  - Debt ratios
  - Liquidity ratios
  - Büyüme oranları (YoY, QoQ)
- Çıktı: `data/features/fundamental/[SYMBOL]_fundamental_features.csv`

---

### 3.3. Makro Feature'lar

**Script:** `src/quanttrade/feature_engineering/macro_features.py`

```bash
python3 src/quanttrade/feature_engineering/macro_features.py
```

**Ne Yapar?**
- Makro değişkenlerden feature'lar üretir:
  - Döviz kuru değişimleri (MoM, YoY)
  - Enflasyon etkisi
  - Faiz oranı değişimleri
  - BIST100 momentum
- Çıktı: `data/features/macro/macro_features.csv`

---

### 3.4. Master DataFrame Builder

**Script:** `src/quanttrade/feature_engineering/master_builder.py`

```bash
python3 src/quanttrade/feature_engineering/master_builder.py
```

**Ne Yapar?**
- ⭐ **TÜM VERİLERİ BİRLEŞTİRİR** ⭐
- Fiyat + Fundamental + Makro feature'ları merge eder
- Future returns hesaplar (60d, 90d, 120d)
- Target variables oluşturur
- Train/test split işaretler
- **Çıktı: `data/master/master_df.csv`** ← Bu dosya model için kullanılır!

**Metadata:** `data/master/master_df_metadata.json`

---

## 🤖 ADIM 4: MODEL TRAINING

```bash
cd /Users/furkanyilmaz/Desktop/QuantTrade/src/quanttrade/models
python3 train_model_pipeline.py
```

**Input:** `data/master/master_df.csv`
**Output:** 
- `model_results/catboost_final_*.cbm`
- `model_results/neutralizer_*.pkl`

---

## 🎯 ADIM 5: PREDICTION

```bash
python3 prediction_engine.py
```

**Output:** `signals/signals_*.csv`

---

## 📈 ADIM 6: BACKTEST

```bash
python3 backtest_strategy.py
```

**Output:** 
- `backtest_results/backtest_*.csv`
- `backtest_results/equity_curve_*.png`

---

## 🚀 Tam Pipeline Otomasyonu

Tüm adımları tek seferde çalıştırmak için:

```bash
#!/bin/bash
cd /Users/furkanyilmaz/Desktop/QuantTrade

echo "============================================"
echo "QUANTTRADE FULL PIPELINE BAŞLIYOR"
echo "============================================"

# 1. DATA SOURCES
echo -e "\n📥 ADIM 1: VERİ TOPLAMA"
python3 src/quanttrade/data_sources/macro_downloader.py
python3 src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py
python3 src/quanttrade/data_sources/mali_tablo.py
python3 src/quanttrade/data_sources/temettü_scraper.py
python3 src/quanttrade/data_sources/split_ratio.py
python3 src/quanttrade/data_sources/kap_announcement_scraper.py

# 2. DATA PROCESSING
echo -e "\n🧹 ADIM 2: VERİ TEMİZLEME"
python3 src/quanttrade/data_processing/ohlcv_cleaner.py
python3 src/quanttrade/data_processing/mali_tablo_normalizer.py
python3 src/quanttrade/data_processing/macro_cleaner.py
python3 src/quanttrade/data_processing/split_cleaner.py
python3 src/quanttrade/data_processing/dividend_cleaner.py
python3 src/quanttrade/data_processing/announcement_cleaner.py

# 3. FEATURE ENGINEERING
echo -e "\n⚙️ ADIM 3: FEATURE ENGINEERING"
python3 src/quanttrade/feature_engineering/price_feature_engineer.py
python3 src/quanttrade/feature_engineering/fundamental_features.py
python3 src/quanttrade/feature_engineering/macro_features.py
python3 src/quanttrade/feature_engineering/master_builder.py

# 4. MODEL TRAINING
echo -e "\n🤖 ADIM 4: MODEL EĞİTİMİ"
cd src/quanttrade/models
python3 train_model_pipeline.py

# 5. PREDICTION
echo -e "\n🎯 ADIM 5: TAHMİN ÜRETME"
python3 prediction_engine.py

# 6. BACKTEST
echo -e "\n📈 ADIM 6: BACKTEST"
python3 backtest_strategy.py

echo -e "\n============================================"
echo "✅ TÜM PIPELINE TAMAMLANDI!"
echo "============================================"
```

Bunu `run_full_pipeline.sh` olarak kaydet ve çalıştır:

```bash
chmod +x run_full_pipeline.sh
./run_full_pipeline.sh
```

---

## 📋 Gereksinimler Kontrol Listesi

### Başlamadan Önce:

- [ ] `.env` dosyası oluşturuldu ve `EVDS_API_KEY` eklendi
- [ ] `config/settings.toml` dosyası ayarlandı
- [ ] Tüm Python paketleri kuruldu (`pip install -r requirements.txt`)
- [ ] Klasör yapısı oluşturuldu:
  ```
  data/
  ├── raw/
  │   ├── macro/
  │   ├── ohlcv/
  │   ├── mali_tablo/
  │   ├── dividend/
  │   ├── split_ratio/
  │   └── announcements/
  ├── processed/
  │   ├── (yukarıdakiyle aynı)
  ├── features/
  │   ├── price/
  │   ├── fundamental/
  │   └── macro/
  └── master/
  ```

---

## ⚠️ Önemli Notlar

### Veri Güncellemesi
- Pipeline'ı **günlük olarak** çalıştırabilirsiniz
- Her çalıştırmada sadece yeni veriler eklenir (incremental)
- Master_df otomatik olarak güncellenir

### Hata Durumları
- Herhangi bir adımda hata olursa, log dosyalarını kontrol edin
- `.log` dosyaları ilgili klasörlerde bulunur
- Script'ler idempotent'tır (tekrar çalıştırılabilir)

### Performans
- İlk çalıştırma **20-30 dakika** sürebilir (tüm geçmiş veri)
- Günlük güncellemeler **2-5 dakika**
- Paralel processing için script'leri ayrı terminallerde çalıştırabilirsiniz

### Veri Boyutları
- Raw data: ~500MB - 1GB
- Processed data: ~300MB - 500MB
- Features: ~200MB - 400MB
- Master_df: ~100MB - 200MB

---

## 🔍 Sorun Giderme

### "EVDS API Key bulunamadı"
```bash
# .env dosyasını kontrol et
cat .env
# Olmalı: EVDS_API_KEY=your_key_here
```

### "Master_df.csv bulunamadı"
```bash
# Tüm önceki adımları çalıştırın
# Özellikle master_builder.py kritik
python3 src/quanttrade/feature_engineering/master_builder.py
```

### "Memory Error"
```bash
# Chunk processing kullanın (script'lerde zaten var)
# Veya RAM'i artırın
```

### Script çalışmıyor
```bash
# Python path'i kontrol et
export PYTHONPATH="${PYTHONPATH}:/Users/furkanyilmaz/Desktop/QuantTrade/src"

# Gerekli paketler kurulu mu?
pip install -r requirements.txt
```

---

## 📊 Çıktı Dosyaları Haritası

```
data/
├── raw/                              # Ham veriler
│   ├── macro/evds_macro_daily.csv
│   ├── ohlcv/AEFES_ohlcv.csv
│   └── mali_tablo/AEFES_financials.csv
│
├── processed/                        # Temizlenmiş veriler
│   ├── ohlcv/AEFES_clean_ohlcv.csv
│   └── mali_tablo/AEFES_normalized.csv
│
├── features/                         # Feature'lar
│   ├── price/AEFES_price_features.csv
│   ├── fundamental/AEFES_fundamental.csv
│   └── macro/macro_features.csv
│
└── master/
    └── master_df.csv                 # ⭐ FINAL OUTPUT
```

---

## 🎯 Sonraki Adımlar

Master_df hazır olduktan sonra:

1. ✅ Explorator Data Analysis (EDA)
2. ✅ Model training
3. ✅ Hyperparameter tuning
4. ✅ Backtest
5. ✅ Live trading

Başarılar! 🚀
