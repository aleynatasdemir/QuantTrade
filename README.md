# 🚀 QuantTrade - Advanced ML Trading System

**Production-Ready AI Trading Platform for Turkish Stock Market (BIST)**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CatBoost](https://img.shields.io/badge/CatBoost-Latest-orange.svg)](https://catboost.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

QuantTrade, akademik standartlarda geliştirilmiş, **Lopez de Prado'nun "Advances in Financial Machine Learning"** metodolojilerini uygulayan, production-ready bir algoritmik trading sistemidir.

## 🎯 Proje Hedefi

**Ana Hedefler:**
- 📊 Makro ekonomik ve finansal verileri toplayarak veri pipeline'ı oluşturma
- 🤖 Advanced ML modelleri ile yüksek performanslı tahmin sistemi
- 📈 Non-overlap backtesting ile gerçekçi performans değerlendirmesi
- 🎯 Production-ready tahmin ve sinyal üretim motoru
- ⚡ Real-time trading capability

**Sistem Özellikleri:**
- ✅ **Triple Barrier Labeling** - Volatilite-bazlı hedef etiketleme
- ✅ **Market Neutralization** - Piyasadan bağımsız alpha üretimi
- ✅ **Purged Time Series CV** - Data leakage önleme
- ✅ **CatBoost Ensemble** - High-performance gradient boosting
- ✅ **Automated Backtesting** - Gerçekçi performans analizi
- ✅ **Signal Generation** - Günlük alım-satım sinyalleri

## 📊 Performans Metrikleri

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| **AUC Score** | 0.779 | Model ayrıştırma gücü |
| **Precision** | 0.706 | Pozitif tahminlerin doğruluk oranı |
| **Hit Rate (Top 5)** | 90% | En iyi 5 hissede kazanma oranı |
| **Lift Factor** | 1.63x | Piyasayı geçme oranı |
| **Sharpe Ratio** | 0.58 | Risk-adjusted getiri |
| **Avg Return** | 94.87% | 120 günlük ortalama getiri |

## 📁 Proje Yapısı

```
QuantTrade/
├── README.md                          # Ana dokümantasyon
├── config/
│   ├── settings.toml                 # Proje ayarları
│   └── kap_symbols_oids_mapping.json # KAP symbol mapping
├── data/
│   ├── master/
│   │   ├── master_df.csv            # Ana veri seti
│   │   └── master_df_metadata.json
│   ├── features/                     # Feature store
│   │   ├── fundamental/
│   │   ├── macro/
│   │   └── price/
│   ├── processed/                    # İşlenmiş veriler
│   └── raw/                          # Ham veriler
├── src/quanttrade/
│   ├── data_sources/                 # Veri kaynakları
│   │   ├── evds_client.py           # TCMB EVDS API
│   │   └── macro_downloader.py
│   ├── data_processing/              # Veri işleme
│   ├── feature_engineering/          # Feature engineering
│   └── models/                       # 🎯 ML Modeller (Ana Sistem)
│       ├── README.md                # Detaylı model dokümantasyonu
│       ├── train_model_pipeline.py  # ✅ Eğitim pipeline'ı
│       ├── prediction_engine.py     # ✅ Tahmin motoru
│       ├── backtest_strategy.py     # ✅ Backtest sistemi
│       ├── test_model.py            # Model test
│       ├── results/                 # Model sonuçları
│       ├── model_results/           # Kaydedilmiş modeller
│       ├── signals/                 # Günlük sinyaller
│       └── backtest_results/        # Backtest raporları
├── docs/                            # Dokümantasyon
│   ├── EVDS_KULLANIM.md
│   └── GUNCELLEME_OZETI.md
└── logs/                            # Log dosyaları
```

## 🚀 Hızlı Başlangıç

### 1. Kurulum

```bash
# Depoyu klonlayın
git clone https://github.com/aleynatasdemir/QuantTrade.git
cd QuantTrade

# Sanal ortam oluşturun
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# veya .venv\Scripts\activate  # Windows

# Bağımlılıkları yükleyin
pip install pandas numpy scikit-learn catboost joblib matplotlib seaborn
```

### 2. Model Eğitimi

```bash
cd src/quanttrade/models
python3 train_model_pipeline.py
```

**Çıktı:**
- ✅ Eğitilmiş CatBoost modeli
- ✅ Feature neutralizer
- ✅ CV sonuçları ve metrikler
- 📊 Out-of-fold performans raporu

### 3. Tahmin Üretimi

```bash
python3 prediction_engine.py
```

**Çıktı:**
- 📊 Güncel piyasa için tahminler
- 🎯 Alım sinyalleri (BUY/HOLD)
- 📈 Skor ve rank listesi
- 💾 CSV formatında kayıt

### 4. Backtest

```bash
python3 backtest_strategy.py
```

**Çıktı:**
- 📈 Equity curve grafiği
- 📊 Performans metrikleri
- 💹 Trade-by-trade sonuçlar
- 📉 Risk analizi

## 📊 Kullanım Örnekleri

### Veri Pipeline

```python
from quanttrade.data_sources.evds_client import EVDSClient

# EVDS'ten makro veri çekme
client = EVDSClient()
df = client.fetch_and_save_default_macro()
```

### Model Eğitimi

```python
from train_model_pipeline import QuantModelTrainer

trainer = QuantModelTrainer(
    data_path='master_df.csv',
    results_dir='model_results'
)
trainer.run_pipeline()
```

### Tahmin Yapma

```python
from prediction_engine import ModelTester

tester = ModelTester(
    model_path='model_results/catboost_final_*.cbm',
    data_path='master_df.csv'
)
results, top_picks = tester.run_analysis(top_n=20)
```

### Backtest

```python
from backtest_strategy import main

# Non-overlap backtest çalıştır
main()  # Otomatik olarak en son modeli kullanır
```

## 🧠 Sistem Detayları

### Triple Barrier Labeling

Geleneksel "120 gün sonra %X getiri" yerine volatilite-bazlı etiketleme:

```python
# Her gün için 3 bariyer:
upper_barrier = price * (1 + 1.5 * volatility)  # Kar al
lower_barrier = price * (1 - 1.0 * volatility)  # Zarar kes
time_barrier = 120 days                          # Max süre

# İlk dokunan bariyer label'ı belirler:
# +1: Upper barrier (kazanç)
# -1: Lower barrier (zarar)
#  0: Time barrier (nötr)
```

### Market Neutralization

Tüm feature'lar BIST100 getirisine karşı nötralize ediliyor:

```python
# Her feature için:
feature_residual = feature - beta * market_return

# Beta, lineer regresyon ile hesaplanır
# Sonuç: Piyasadan bağımsız, pure alpha
```

### Purged Time Series CV

Data leakage'ı önlemek için özel CV:

```
Timeline:
[---Train---|PURGE|Test|EMBARGO|---Train---|...]
            ↑     ↑    ↑       ↑
            80    100  120     125

PURGE: Test öncesi 20 gün çıkarılır
EMBARGO: Test sonrası %5 çıkarılır
```

## 📈 Model Performansı

### Cross-Validation Sonuçları

```
Fold 1/5: AUC = 0.777
Fold 2/5: AUC = 0.760
Fold 3/5: AUC = 0.771
Fold 4/5: AUC = 0.803
Fold 5/5: AUC = 0.783
----------------------------
Mean AUC: 0.779 ± 0.015
```

### Score Bucket Analizi

| Score Range | Hit Rate | Mean Return |
|-------------|----------|-------------|
| >90% | 92.9% | 63.5% |
| 70-80% | 79.7% | 63.8% |
| 40-50% | 43.9% | 64.1% |
| <10% | 3.4% | 25.5% |

**Yorum:** Model skorları ile gerçek performans arasında güçlü korelasyon var. Model well-calibrated.

### Backtest Sonuçları

**12 Trade Dönemi (3.7 yıl):**
- 📊 Ortalama Strateji Getirisi: **94.87%**
- 📉 Ortalama Piyasa Getirisi: **58.12%**
- 🚀 Lift Factor: **1.63x**
- 📈 Sharpe Ratio: **0.58**
- 🎯 Win Rate: **83%** (10/12)

## 🛠️ Teknoloji Stack

**Core:**
- Python 3.11+
- CatBoost - Gradient boosting
- Scikit-learn - ML utilities
- Pandas/NumPy - Data manipulation

**Data Sources:**
- TCMB EVDS - Makro ekonomik veriler
- Yahoo Finance - Hisse senedi verileri
- KAP - Finansal tablolar

**Advanced Techniques:**
- Triple Barrier Labeling
- Market Neutralization
- Purged CV
- Non-overlap Backtesting

## 📋 Tamamlanan Özellikler

### ✅ Veri Altyapısı
- [x] EVDS API entegrasyonu
- [x] Yahoo Finance veri çekimi
- [x] KAP mali tablo verileri
- [x] Master DataFrame oluşturma
- [x] Feature store yapısı

### ✅ Feature Engineering
- [x] Teknik indikatörler (RSI, MACD, SMA, volatilite)
- [x] Fundamental features (ROE, ROA, P/E, Debt/Equity)
- [x] Makro features (USD/TRY, CPI, faiz, M2)
- [x] Feature neutralization (market beta removal)

### ✅ ML Pipeline
- [x] Triple barrier labeling
- [x] Purged time series CV
- [x] CatBoost model training
- [x] Feature neutralization
- [x] Model evaluation & metrics

### ✅ Production Systems
- [x] Prediction engine (daily signals)
- [x] Backtest framework (non-overlap)
- [x] Model persistence & loading
- [x] Signal generation & CSV export

### ✅ Documentation
- [x] Comprehensive README
- [x] Model documentation
- [x] API reference
- [x] Usage examples

## 🚧 Gelecek Geliştirmeler

### Öncelikli
- [ ] Real-time data pipeline
- [ ] Model monitoring dashboard
- [ ] Automated retraining
- [ ] A/B testing framework

### Gelişmiş Özellikler
- [ ] Deep learning models (LSTM, Transformer)
- [ ] Alternative data sources (sentiment, options)
- [ ] Portfolio optimization
- [ ] Risk management (VaR, CVaR)
- [ ] Multi-timeframe analysis

### Production
- [ ] API endpoint (Flask/FastAPI)
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Cloud deployment (AWS/GCP)

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen:
1. Bu depoyu fork edin
2. Feature branch'i oluşturun (`git checkout -b feature/AmazingFeature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some AmazingFeature'`)
4. Branch'inizi push edin (`git push origin feature/AmazingFeature`)
5. Pull Request açın

## 📚 Referanslar

**Akademik:**
- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
- Lopez de Prado, M. (2020). *Machine Learning for Asset Managers*. Cambridge.
- Jansen, S. (2020). *Machine Learning for Algorithmic Trading* (2nd ed.). Packt.

**Linkler:**
- [CatBoost Documentation](https://catboost.ai/)
- [EVDS API](https://evds2.tcmb.gov.tr/)
- [Detailed Model Documentation](src/quanttrade/models/README.md)

## ⚠️ Disclaimer

**Bu sistem sadece eğitim ve araştırma amaçlıdır.**

- ❌ Yatırım tavsiyesi değildir
- ❌ Gelecek performans garantisi yoktur
- ❌ Geçmiş performans gelecek performansı göstermez
- ⚠️ Gerçek para ile kullanmadan önce kapsamlı test yapın
- ⚠️ Riski göze alabileceğiniz kadar yatırım yapın
- ⚠️ Profesyonel danışmanlık alın

**Yasal Sorumluluk:**
Bu sistemin kullanımından doğan hiçbir kayıp veya zararda geliştirici sorumlu tutulamaz.

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakın.

## 📧 İletişim

- 💬 GitHub Issues
- 📝 Pull Requests
- 📧 Email: quanttrade@example.com

---

**⭐ Projeyi beğendiyseniz yıldız vermeyi unutmayın!**

**Happy Trading! 🚀📈💰**
