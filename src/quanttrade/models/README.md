# 🚀 QuantTrade - Advanced ML Trading System

## 📋 İçindekiler
- [Genel Bakış](#-genel-bakış)
- [Sistem Mimarisi](#-sistem-mimarisi)
- [Kurulum](#-kurulum)
- [Kullanım Kılavuzu](#-kullanım-kılavuzu)
- [Model Pipeline Detayları](#-model-pipeline-detayları)
- [Backtest Sonuçları](#-backtest-sonuçları)
- [API Referansı](#-api-referansı)
- [İleri Seviye Konular](#-i̇leri-seviye-konular)

---

## 🎯 Genel Bakış

QuantTrade, Türkiye hisse senedi piyasası için geliştirilmiş, akademik standartlarda bir **makine öğrenmesi tabanlı alım-satım sistemi**dir. Sistem, Lopez de Prado'nun "Advances in Financial Machine Learning" kitabındaki metodolojileri uygular.

### ✨ Temel Özellikler

- **Triple Barrier Labeling**: Gelecek getirileri hedef olarak değil, volatilite-bazlı bariyerlerle etiketleme
- **Market Neutralization**: Tüm feature'lar BIST100 getirisine karşı nötralize ediliyor
- **Purged Time Series CV**: Data leakage'ı önlemek için embargo ve purging
- **CatBoost Ensemble**: Gradient boosting ile yüksek performanslı tahminler
- **Non-Overlap Backtest**: Gerçekçi backtest, overlap yok
- **Production-Ready**: Model kaydetme, tahmin motoru ve sinyal üretimi

### 📊 Performans Metrikleri

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| **AUC Score** | 0.779 | Model ayrıştırma gücü |
| **Precision** | 0.706 | Pozitif tahminlerin doğruluk oranı |
| **Recall** | 0.703 | Gerçek fırsatları yakalama oranı |
| **Hit Rate (Top 5)** | 0.90 | En iyi 5 tahminde kazanma oranı |
| **Lift Factor** | 1.63x | Piyasayı geçme oranı |
| **Sharpe Ratio** | 0.58 | Risk-adjusted getiri |

---

## 🏗️ Sistem Mimarisi

### Dosya Yapısı

```
src/quanttrade/models/
├── train_model_pipeline.py    # Ana eğitim pipeline'ı
├── prediction_engine.py        # Gerçek zamanlı tahmin motoru
├── backtest_strategy.py        # Backtest sistemi
├── test_model.py              # Model test ve tahmin kodu
├── results/                   # Eğitim sonuçları
│   ├── *.pkl                  # Kaydedilmiş modeller
│   ├── *.png                  # Performans grafikleri
│   └── FINAL_MODEL_COMPARISON.csv
├── model_results/             # Pipeline çıktıları
│   ├── catboost_final_*.cbm   # CatBoost modeli
│   └── neutralizer_*.pkl      # Feature neutralizer
├── signals/                   # Günlük tahmin sinyalleri
│   └── signals_*.csv
└── backtest_results/          # Backtest sonuçları
    ├── backtest_*.csv
    └── equity_curve_*.png
```

### Veri Akışı

```
master_df.csv
    ↓
[Triple Barrier Labeling]
    ↓
[Feature Selection & Cleaning]
    ↓
[Market Neutralization]
    ↓
[Purged Time Series CV]
    ↓
[CatBoost Training]
    ↓
[Model Evaluation]
    ↓
[Model Saving] → [Prediction Engine] → signals/
                ↓
         [Backtest] → backtest_results/
```

---

## 🔧 Kurulum

### Gereksinimler

```bash
# Python 3.8+
python --version

# Gerekli kütüphaneler
pip install pandas numpy scikit-learn catboost joblib matplotlib seaborn
```

### Veri Hazırlığı

Sistem `master_df.csv` dosyasını bekler. Bu dosya şu kolonları içermelidir:

**Zorunlu Kolonlar:**
- `symbol`: Hisse senedi kodu (str)
- `date`: Tarih (datetime)
- `price_close`: Kapanış fiyatı (float)
- `macro_bist100_roc_5d`: BIST100 5 günlük getirisi (float)
- `future_return_120d`: 120 gün sonraki getiri (float)

**Feature Kolonları:**
- `price_*`: Fiyat özellikleri (open, high, low, volume, sma, rsi, vb.)
- `fund_*`: Fundamental özellikler (roe, roa, debt_to_equity, vb.)
- `macro_*`: Makro ekonomik özellikler (usd_try, cpi, m2, vb.)

---

## 🎮 Kullanım Kılavuzu

### 1. Model Eğitimi (Training Pipeline)

```bash
cd src/quanttrade/models
python3 train_model_pipeline.py
```

**Ne Yapar?**
1. ✅ `master_df.csv` dosyasını yükler
2. ✅ Triple barrier labeling ile hedef değişken oluşturur
3. ✅ Feature'ları temizler ve seçer (sadece numeric)
4. ✅ Market neutralization uygular
5. ✅ 5-fold Purged Time Series CV ile eğitir
6. ✅ Her fold için AUC skorunu yazdırır
7. ✅ Out-of-fold performansı raporlar
8. ✅ Final modeli tüm veri ile eğitir
9. ✅ Model ve neutralizer'ı kaydeder

**Çıktılar:**
```
model_results/
├── catboost_final_20251120_022613.cbm
└── neutralizer_20251120_022613.pkl
```

**Örnek Çıktı:**
```
>> Veriyi yüklüyorum...
>> Triple-Barrier target üretiliyor...
>> Feature seçimi...
   Toplam 45 numeric feature seçildi
>> Feature neutralization (market'e karşı)...
>> Purged TimeSeries CV ile eğitim...

--- Fold 1/5 ---
Fold AUC: 0.777

--- Fold 2/5 ---
Fold AUC: 0.760

...

=== Classification Metrics ===
AUC     : 0.779
Precision: 0.706
Recall   : 0.703
F1       : 0.705
```

### 2. Tahmin Motoru (Prediction Engine)

```bash
python3 prediction_engine.py
```

**Ne Yapar?**
1. ✅ En son kaydedilmiş modeli ve neutralizer'ı yükler
2. ✅ `master_df.csv`'den en son tarihteki verileri alır
3. ✅ Feature'ları hazırlar ve neutralize eder
4. ✅ Her hisse için tahmin skoru üretir (0-1 arası)
5. ✅ Skorlara göre sıralar ve sinyal oluşturur
6. ✅ Sonuçları CSV olarak kaydeder

**Çıktılar:**
```
signals/
└── signals_20251117_20251120_023319.csv
```

**Örnek Çıktı:**
```
>> Son modeli ve neutralizer'ı buluyorum...
>> Veriyi yüklüyorum...
>> Tahmin yapılacak tarih: 2025-11-17  (satır sayısı: 33)
>> Neutralizer uygulanıyor...
>> Model tahmin üretiyor...

✅ Sinyaller kaydedildi: signals/signals_20251117_20251120_023319.csv
>> BUY sinyali sayısı (threshold=0.7): 0

>> En yüksek skorlu ilk 20 hisse:
symbol       date    score  rank  percentile  bucket signal
 VESTL 2025-11-17 0.511536     1    1.000000       5   HOLD
 PETKM 2025-11-17 0.400684     2    0.969697       4   HOLD
 EREGL 2025-11-17 0.369666     3    0.939394       3   HOLD
```

**Konfigürasyon:**
```python
# prediction_engine.py içinde
BUY_THRESHOLD = 0.70  # Alım sinyali eşiği (0-1)
TOP_N_PRINT = 20      # Konsolda gösterilecek hisse sayısı
```

### 3. Backtest Stratejisi

```bash
python3 backtest_strategy.py
```

**Ne Yapar?**
1. ✅ Tüm geçmiş veri için skorlar üretir
2. ✅ Her 120 günde bir rebalance yapar (non-overlap)
3. ✅ Her rebalance'da en yüksek skorlu TOP_K hisseyi alır
4. ✅ 120 gün sonraki gerçek getiriyi kaydeder
5. ✅ Strateji vs piyasa performansını karşılaştırır
6. ✅ Equity curve çizer ve CSV'ye kaydeder

**Çıktılar:**
```
backtest_results/
├── backtest_nonoverlap_20251120_024640.csv
└── equity_curve_nonoverlap_20251120_024640.png
```

**Örnek Çıktı:**
```
===== NON-OVERLAP BACKTEST ÖZET =====
Trade sayısı                : 12
Ortalama strateji getirisi  : 0.9487  (94.87%)
Ortalama piyasa getirisi    : 0.5812  (58.12%)
Lift (mean_strat / mean_mkt): 1.63
Sharpe (trade bazlı)        : 0.58
Ortalama hit rate (TOP 5): 0.90
```

**Konfigürasyon:**
```python
# backtest_strategy.py içinde
HORIZON = 120           # Holding period (gün)
TOP_K = 5              # Her rebalance'da alınan hisse sayısı
MIN_STOCKS_PER_DAY = 5 # Minimum universe boyutu
```

### 4. Model Test ve Analiz

```bash
python3 test_model.py
```

**Ne Yapar?**
- Eğitilmiş XGBoost/RandomForest/LightGBM modellerini test eder
- Güncel piyasada tahminler üretir
- Olasılıkları ve güven seviyelerini gösterir

---

## 🧠 Model Pipeline Detayları

### 1. Triple Barrier Labeling

**Neden?**
Geleneksel yöntemde "120 gün sonra %30 artarsa 1, yoksa 0" şeklinde etiketleme yapılır. Bu:
- ❌ Zaman bilgisini kaybeder (5 günde %30 vs 119 günde %30)
- ❌ Volatilite farklılıklarını görmez
- ❌ Risk/reward oranını dikkate almaz

**Triple Barrier Yaklaşımı:**
```python
# Her gün için 3 bariyer belirlenir:
upper_barrier = price * (1 + up_mult * volatility)   # Kar al noktası
lower_barrier = price * (1 - down_mult * volatility) # Zarar kes noktası
time_barrier = 120 days                               # Maksimum süre

# Label:
# +1: Upper barrier'a ilk dokunan
# -1: Lower barrier'a ilk dokunan
#  0: Time barrier'a ulaşan veya nötr
```

**Parametreler:**
```python
HORIZON = 120          # Maksimum holding period (gün)
VOL_LOOKBACK = 20      # Volatilite hesaplama penceresi
UP_MULT = 1.5          # Üst bariyer çarpanı
DOWN_MULT = 1.0        # Alt bariyer çarpanı
```

### 2. Feature Engineering

**Feature Seçimi:**
```python
# ✅ Kullanılan Feature'lar:
- price_* : Teknik göstergeler (RSI, MACD, SMA, volatilite)
- fund_*  : Fundamental veriler (ROE, ROA, P/E, Debt/Equity)
- macro_* : Makro ekonomik veriler (USD/TRY, CPI, faiz, M2)

# ❌ Çıkarılan Kolonlar:
- future_return_* : Data leakage
- y_*             : Eski target kolonları
- date, symbol    : Meta kolonlar
- period, announcement_date : Text kolonları
```

**Temizleme:**
```python
# 1. Sadece numeric kolonlar seçilir
for c in df.columns:
    if pd.api.types.is_numeric_dtype(df[c]):
        feature_cols.append(c)

# 2. Inf değerler NaN yapılır
X = X.replace([np.inf, -np.inf], np.nan)

# 3. NaN'lar median ile doldurulur
X = X.fillna(X.median())
```

### 3. Market Neutralization

**Neden?**
Piyasa genel yükselişte/düşüşte olduğunda tüm hisseler etkilenir. Biz **piyasadan bağımsız alpha** arıyoruz.

**Nasıl?**
Her feature için BIST100 getirisine karşı lineer regresyon:

```python
class FeatureNeutralizer:
    def fit(self, X, market_ret):
        for feature in X.columns:
            # feature = beta * market_ret + alpha + residual
            lr = LinearRegression()
            lr.fit(market_ret, X[feature])
            self.models[feature] = lr
    
    def transform(self, X, market_ret):
        for feature in X.columns:
            predicted = lr.predict(market_ret)
            X[feature] = X[feature] - predicted  # Residual (alpha)
        return X
```

**Sonuç:**
- Her feature artık piyasadan bağımsız
- Model sadece relative (göreceli) değerleri öğrenir
- Market beta'dan arındırılmış pure alpha

### 4. Purged Time Series Cross Validation

**Problem:**
Normal CV'de train/test split overlap olabilir → data leakage

**Çözüm:**
```python
@dataclass
class PurgedTimeSeriesSplit:
    n_splits: int = 5
    purge_window: int = 20      # Test öncesi purge edilecek gün sayısı
    embargo_pct: float = 0.05   # Test sonrası embargo (%5)
```

**Nasıl Çalışır?**
```
Timeline:
[-------Train-------|PURGE|Test|EMBARGO|-------Train-------|...]

1. Test seti belirlenir (örn. Gün 100-120)
2. PURGE: Gün 80-99 eğitimden çıkarılır (test'e çok yakın)
3. EMBARGO: Gün 121-125 eğitimden çıkarılır (test sonrası bilgi sızıntısı)
4. Kalan veriler train olur
```

**Neden Önemli?**
- ✅ Gerçek dünya senaryosunu simüle eder
- ✅ Data leakage'ı tamamen önler
- ✅ Daha güvenilir performans metrikleri

### 5. CatBoost Model

**Neden CatBoost?**
- ✅ Ordered boosting → data leakage riski düşük
- ✅ Native categorical support (kullanmıyoruz ama)
- ✅ GPU acceleration
- ✅ Robust to overfitting
- ✅ Fast training & inference

**Hiperparametreler:**
```python
model = CatBoostClassifier(
    loss_function="Logloss",
    eval_metric="AUC",
    depth=6,                     # Tree derinliği (overfitting kontrolü)
    learning_rate=0.05,          # Küçük = daha stable
    iterations=500,              # Boosting round sayısı
    l2_leaf_reg=3.0,            # L2 regularization
    random_seed=42,
    verbose=False,
    class_weights=[1.0, weight] # Imbalanced data için
)
```

**Class Weighting:**
```python
# Pozitif sınıf (label=1) azsa ağırlığı artır
n_neg = (y_train == 0).sum()
n_pos = (y_train == 1).sum()
pos_weight = n_neg / n_pos
```

---

## 📈 Backtest Sonuçları

### Methodology

**Non-Overlap Backtesting:**
```python
# Her 120 günde bir:
1. Bugünkü tüm hisseler için skor üret
2. En yüksek skorlu TOP_K hisseyi seç
3. 120 gün boyunca hold et
4. Gerçek getiriyi kaydet
5. Bir sonraki 120. güne git (overlap YOK)
```

**Örnek Timeline:**
```
Gün 1   → Hisse seç → 120 gün hold → Getiri kaydet
Gün 121 → Hisse seç → 120 gün hold → Getiri kaydet
Gün 241 → Hisse seç → 120 gün hold → Getiri kaydet
...
```

### Performans Analizi

**12 Trade Dönemi (3.7 yıl):**

| Metrik | Strateji | Piyasa | Fark |
|--------|----------|--------|------|
| **Ortalama Getiri** | %94.87 | %58.12 | +%36.75 |
| **Toplam Getiri** | %1,138 | %697 | +%441 |
| **Kazanan Trade** | 10/12 | - | %83 |
| **Max Win** | %150+ | - | - |
| **Sharpe Ratio** | 0.58 | - | - |

**Score Bucket Analizi:**
```
Bucket | Hit Rate | Mean Return
-------|----------|-------------
  >90% |   92.9%  |    63.5%
70-80% |   79.7%  |    63.8%
40-50% |   43.9%  |    64.1%
  <10% |    3.4%  |    25.5%
```

**Interpretation:**
- Model güveni arttıkça hit rate artıyor ✅
- En yüksek skorlar %93 başarı oranı gösteriyor ✅
- Düşük skorlar gerçekten de kötü (3.4% hit rate) ✅

### Risk Analizi

**Strengths:**
- ✅ Yüksek lift factor (1.63x)
- ✅ Tutarlı pozitif alpha
- ✅ İyi calibrated (skor vs performans uyumlu)
- ✅ Non-overlap methodology (gerçekçi)

**Risks:**
- ⚠️ Sample size küçük (12 trade)
- ⚠️ Survivorship bias olabilir
- ⚠️ Transaction costs dahil değil
- ⚠️ Slippage modellenmemiş
- ⚠️ Market regime değişikliği riski

---

## 🔬 API Referansı

### FeatureNeutralizer

```python
class FeatureNeutralizer(BaseEstimator, TransformerMixin):
    """
    Feature'ları market return'e karşı nötralize eder.
    """
    def __init__(self, market_ret: pd.Series = None):
        """
        Args:
            market_ret: Piyasa getirisi serisi (eğitim için)
        """
        
    def fit(self, X: pd.DataFrame, y=None):
        """
        Her feature için market_ret'e karşı lineer regresyon fit eder.
        
        Args:
            X: Feature matrix
            y: Ignored
            
        Returns:
            self
        """
        
    def transform(self, X: pd.DataFrame, market_ret: pd.Series = None):
        """
        Feature'ları nötralize eder.
        
        Args:
            X: Feature matrix
            market_ret: Yeni market return (opsiyonel, prediction için)
            
        Returns:
            X_neutral: Nötralize edilmiş feature matrix
        """
```

### PurgedTimeSeriesSplit

```python
@dataclass
class PurgedTimeSeriesSplit(BaseCrossValidator):
    """
    Time series CV with purging and embargo.
    """
    n_splits: int = 5           # Fold sayısı
    purge_window: int = 10      # Test öncesi purge edilecek sample sayısı
    embargo_pct: float = 0.0    # Test sonrası embargo oranı
    time_index: Optional[pd.Index] = None
    
    def split(self, X, y=None, groups=None):
        """
        Train/test split'leri generate eder.
        
        Yields:
            train_indices, test_indices
        """
```

### Utility Functions

```python
def triple_barrier_labels(
    df: pd.DataFrame,
    price_col: str,
    horizon: int,
    vol_span: int,
    up_mult: float,
    down_mult: float
) -> pd.Series:
    """
    Triple barrier labeling.
    
    Args:
        df: Hisse verisi (tek symbol)
        price_col: Fiyat kolonu adı
        horizon: Maksimum holding period
        vol_span: Volatilite penceresi
        up_mult: Üst bariyer çarpanı
        down_mult: Alt bariyer çarpanı
        
    Returns:
        labels: pd.Series (-1, 0, 1)
    """

def get_latest_file(pattern: str) -> str:
    """
    En son değiştirilmiş dosyayı bulur.
    
    Args:
        pattern: Glob pattern (örn: "model_results/*.cbm")
        
    Returns:
        path: Dosya yolu
    """
```

---

## 🎓 İleri Seviye Konular

### 1. Feature Engineering İyileştirmeleri

**Eklenebilecek Feature'lar:**

```python
# 1. Momentum Indicators
df['momentum_20d'] = df['price_close'].pct_change(20)
df['momentum_60d'] = df['price_close'].pct_change(60)

# 2. Volume Indicators
df['volume_ratio'] = df['price_volume'] / df['price_volume'].rolling(20).mean()
df['price_volume_corr'] = df['price_close'].rolling(20).corr(df['price_volume'])

# 3. Volatility Regime
df['vol_regime'] = (df['price_vol_20d'] / df['price_vol_60d']) - 1

# 4. Relative Performance
df['vs_market'] = df['price_return_20d'] - df['macro_bist100_roc_20d']
df['vs_sector'] = df['price_return_20d'] - df['sector_return_20d']

# 5. Fundamental Ratios
df['pe_ratio'] = df['price_close'] / df['fund_eps']
df['pb_ratio'] = df['price_close'] / df['fund_book_value_per_share']
df['peg_ratio'] = df['pe_ratio'] / df['fund_earnings_growth']
```

### 2. Model Ensemble

**Çoklu Model Birleştirme:**

```python
# 1. Train multiple models
models = {
    'catboost': CatBoostClassifier(...),
    'xgboost': XGBClassifier(...),
    'lightgbm': LGBMClassifier(...)
}

# 2. Get predictions
predictions = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    predictions[name] = model.predict_proba(X_test)[:, 1]

# 3. Ensemble (weighted average)
weights = {'catboost': 0.5, 'xgboost': 0.3, 'lightgbm': 0.2}
ensemble_pred = sum(weights[name] * predictions[name] 
                   for name in models.keys())
```

### 3. Dynamic Position Sizing

**Kelly Criterion:**

```python
def kelly_criterion(win_rate, avg_win, avg_loss):
    """
    Optimal position size hesapla.
    
    f* = (p * b - q) / b
    p = win rate
    q = 1 - p
    b = avg_win / avg_loss
    """
    if avg_loss == 0:
        return 0
    b = avg_win / avg_loss
    f = (win_rate * b - (1 - win_rate)) / b
    return max(0, min(f, 0.25))  # Cap at 25%

# Her hisse için
for symbol in portfolio:
    score = predictions[symbol]
    historical_win_rate = backtest_data[symbol]['win_rate']
    kelly_size = kelly_criterion(historical_win_rate, ...)
    position_size = base_position * (score ** 2) * kelly_size
```

### 4. Risk Management

**Stop Loss ve Take Profit:**

```python
# Triple barrier'daki gibi dinamik
stop_loss = entry_price * (1 - DOWN_MULT * volatility)
take_profit = entry_price * (1 + UP_MULT * volatility)

# Fixed percentage
stop_loss = entry_price * 0.90   # 10% stop
take_profit = entry_price * 1.30  # 30% profit
```

**Portfolio Level Limits:**

```python
# Max drawdown kontrolü
if portfolio_value < peak_value * (1 - MAX_DRAWDOWN):
    # Reduce positions or stop trading
    pass

# Correlation kontrolü
if portfolio_correlation > 0.7:
    # Diversify more
    pass

# Sector exposure limiti
for sector in sectors:
    if sector_exposure[sector] > 0.30:  # Max 30% per sector
        # Reduce sector exposure
        pass
```

### 5. Live Trading Entegrasyonu

**Örnek Yapı:**

```python
import schedule
import time

def daily_trading_routine():
    """
    Her gün piyasa kapanışında çalış.
    """
    # 1. Veriyi güncelle
    update_master_df()
    
    # 2. Tahminleri üret
    os.system('python3 prediction_engine.py')
    
    # 3. Sinyalleri oku
    signals = pd.read_csv('signals/latest.csv')
    buy_signals = signals[signals['signal'] == 'BUY']
    
    # 4. Order'ları gönder (broker API)
    for idx, row in buy_signals.iterrows():
        symbol = row['symbol']
        score = row['score']
        position_size = calculate_position_size(symbol, score)
        
        # broker.place_order(symbol, 'BUY', position_size)
        print(f"BUY {symbol}: {position_size} shares (score: {score:.3f})")
    
    # 5. Mevcut pozisyonları kontrol
    check_exit_conditions()

# Schedule
schedule.every().day.at("18:30").do(daily_trading_routine)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 6. Monitoring ve Alerting

```python
def monitor_model_performance():
    """
    Model performansını izle ve uyar.
    """
    recent_predictions = load_recent_predictions(days=30)
    
    # 1. Calibration check
    expected_hit_rate = recent_predictions['score'].mean()
    actual_hit_rate = recent_predictions['actual_win'].mean()
    
    if abs(expected_hit_rate - actual_hit_rate) > 0.15:
        alert("Model calibration degraded!")
    
    # 2. Score distribution check
    recent_avg_score = recent_predictions['score'].mean()
    if recent_avg_score < 0.30:  # Too conservative
        alert("Model scores unusually low!")
    
    # 3. Feature drift
    current_features = get_current_feature_stats()
    training_features = load_training_feature_stats()
    
    for feature in current_features:
        psi = calculate_psi(current_features[feature], 
                           training_features[feature])
        if psi > 0.25:  # Population Stability Index
            alert(f"Feature drift detected: {feature}")

def alert(message):
    """Send alert via email/SMS/Slack"""
    print(f"🚨 ALERT: {message}")
    # Send to monitoring system
```

---

## 📚 Referanslar

### Akademik Kaynaklar

1. **Lopez de Prado, M.** (2018). *Advances in Financial Machine Learning*. Wiley.
   - Triple barrier labeling
   - Purged cross-validation
   - Feature importance

2. **Lopez de Prado, M.** (2020). *Machine Learning for Asset Managers*. Cambridge University Press.
   - Portfolio optimization
   - Risk management

3. **Jansen, S.** (2020). *Machine Learning for Algorithmic Trading* (2nd ed.). Packt.
   - Feature engineering
   - Backtesting methodologies

### Yararlı Linkler

- [CatBoost Documentation](https://catboost.ai/docs/)
- [Scikit-learn API](https://scikit-learn.org/stable/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Advances in Financial ML (GitHub)](https://github.com/hudson-and-thames/mlfinlab)

---

## 🤝 Katkıda Bulunma

### Geliştirme Yapılacak Alanlar

1. **Feature Engineering**
   - [ ] Alternative data sources (sentiment, options, insider trading)
   - [ ] Time series features (ARIMA residuals, seasonality)
   - [ ] Graph features (supply chain, ownership network)

2. **Model İyileştirmeleri**
   - [ ] Deep learning (LSTM, Transformer)
   - [ ] Meta-labeling (model of models)
   - [ ] Online learning (incremental updates)

3. **Risk Management**
   - [ ] Value at Risk (VaR) calculation
   - [ ] Conditional VaR (CVaR)
   - [ ] Stress testing scenarios

4. **Production Features**
   - [ ] Real-time data pipeline
   - [ ] Model monitoring dashboard
   - [ ] Automated retraining
   - [ ] A/B testing framework

---

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

---

## 📞 İletişim

Sorularınız veya önerileriniz için:
- GitHub Issues
- Pull Requests
- Email: quanttrade@example.com

---

## 📝 Lisans

MIT License - Detaylar için `LICENSE` dosyasına bakın.

---

## 🎉 Teşekkürler

Bu proje şu kaynaklardan ilham almıştır:
- Lopez de Prado'nun çalışmaları
- Hudson & Thames MLFinLab
- Türkiye fintech topluluğu

**Happy Trading! 🚀📈💰**
