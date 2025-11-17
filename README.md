# QuantTrade 📈

**BIST100 için ML tabanlı kantitatif alım-satım sistemi**

QuantTrade, Türkiye borsasında (BIST100) makine öğrenmesi teknikleri kullanarak algoritmik trading stratejileri geliştirmek için tasarlanmış açık kaynaklı bir projedir.

## 🎯 Proje Hedefi

TCMB EVDS, Yahoo Finance gibi kaynaklardan makroekonomik ve finansal verileri toplayarak, makine öğrenmesi modelleri ile alım-satım sinyalleri üreten, backtest edilebilen ve genişletilebilir bir sistem kurmak.

## 📁 Proje Yapısı

```
quanttrade/
├── README.md                 # Bu dosya
├── .gitignore               # Git ignore kuralları
├── .env                     # Ortam değişkenleri (API anahtarları)
├── requirements.txt         # Python bağımlılıkları
├── config/
│   └── settings.toml        # Proje ayarları
├── data/
│   └── raw/
│       └── macro/           # Ham makro veriler
├── src/
│   └── quanttrade/
│       ├── __init__.py
│       ├── config.py        # Konfigürasyon yönetimi
│       └── data_sources/
│           ├── __init__.py
│           ├── evds_client.py       # EVDS API client
│           └── macro_downloader.py  # Makro veri indirici
├── notebooks/               # Jupyter notebook'lar
└── logs/                    # Log dosyaları
```

## 🚀 Kurulum

### 1. Depoyu Klonlayın

```bash
git clone https://github.com/aleynatasdemir/QuantTrade.git
cd QuantTrade
```

### 2. Sanal Ortam Oluşturun (Önerilen)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarlayın

`.env` dosyasını düzenleyin ve EVDS API anahtarınızı ekleyin:

```env
EVDS_API_KEY=your_actual_api_key_here
```

**EVDS API Anahtarı Nasıl Alınır:**
1. [TCMB EVDS](https://evds2.tcmb.gov.tr/) sitesine gidin
2. Üye olun (ücretsiz)
3. Profilim > API Anahtarım bölümünden anahtarınızı alın

### 5. Ayarları Kontrol Edin

`config/settings.toml` dosyasını inceleyip gerekirse düzenleyin:
- Tarih aralıklarını (`start_date`, `end_date`)
- EVDS seri kodlarını kontrol edin

## 📊 Kullanım

### Makro Veri İndirme

EVDS'ten makroekonomik verileri indirmek için:

```bash
python src/quanttrade/data_sources/macro_downloader.py
```

Bu komut:
- `config/settings.toml` dosyasındaki ayarları okur
- EVDS API'den belirtilen serileri çeker
- Verileri `data/raw/macro/evds_macro_daily.csv` dosyasına kaydeder

### Python Kodu Olarak Kullanım

```python
from quanttrade.data_sources.evds_client import EVDSClient

# Client oluştur
client = EVDSClient()

# Varsayılan makro verileri çek
output_path = client.fetch_and_save_default_macro()
print(f"Veriler kaydedildi: {output_path}")

# Özel seri çekme
df = client.fetch_series(
    series_codes=["TP.DK.USD.A.YTL", "TP.XU100"],
    start_date="2023-01-01",
    end_date="2023-12-31"
)
print(df.head())
```

## 📝 Faz 1 - Adım 1: EVDS Makro Veri Altyapısı

### Tamamlanan Özellikler ✅

- [x] Proje klasör yapısı
- [x] `.env` ve `settings.toml` konfigürasyonu
- [x] `config.py` - Ayar yönetimi
- [x] `evds_client.py` - EVDS API entegrasyonu
- [x] `macro_downloader.py` - Veri indirme script'i
- [x] Kapsamlı dokümantasyon

### Çekilen Makro Seriler

| Değişken | EVDS Kodu | Açıklama |
|----------|-----------|----------|
| `usd_try` | TP.DK.USD.A.YTL | Dolar/TL kuru |
| `eur_try` | TP.DK.EUR.A.YTL | Euro/TL kuru |
| `bist100` | TP.XU100 | BIST100 endeksi |
| `m2` | TP.M2.YTL | M2 para arzı |
| `cpi` | TP.FG.J0 | TÜFE (Enflasyon) |

**Not:** S&P500 EVDS'te mevcut olmayabilir, alternatif kaynaklardan (Yahoo Finance gibi) çekilecektir.

## 🛠️ Teknoloji Stack'i

- **Python 3.11+**
- **evdspy** - TCMB EVDS API client
- **pandas** - Veri manipülasyonu
- **python-dotenv** - Ortam değişkenleri yönetimi
- **toml** - Konfigürasyon dosyası parsing

## 📋 Gelecek Adımlar

### Faz 1 - Veri Altyapısı
- [ ] Yahoo Finance entegrasyonu (BIST100 hisse verileri)
- [ ] S&P500 verisi çekme
- [ ] Veri kalite kontrolü ve temizleme
- [ ] Veri güncelleme otomasyonu

### Faz 2 - Feature Engineering
- [ ] Teknik indikatörler (RSI, MACD, Bollinger Bands)
- [ ] Makro feature'lar (moving averages, volatility)
- [ ] Lag features

### Faz 3 - ML Model Geliştirme
- [ ] Baseline modeller (Logistic Regression, Random Forest)
- [ ] Gelişmiş modeller (XGBoost, LSTM)
- [ ] Hyperparameter tuning

### Faz 4 - Backtesting & Deployment
- [ ] Backtesting framework
- [ ] Risk yönetimi
- [ ] Paper trading
- [ ] Deployment

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen:
1. Bu depoyu fork edin
2. Feature branch'i oluşturun (`git checkout -b feature/AmazingFeature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some AmazingFeature'`)
4. Branch'inizi push edin (`git push origin feature/AmazingFeature`)
5. Pull Request açın

## ⚠️ Uyarılar

- **Finansal Tavsiye Değildir:** Bu proje eğitim ve araştırma amaçlıdır. Gerçek para ile işlem yapmadan önce profesyonel danışmanlık alın.
- **API Limitleri:** EVDS API'nin kullanım limitleri vardır, aşırı istek yapmaktan kaçının.
- **Veri Doğruluğu:** Verilerin doğruluğunu her zaman kontrol edin.

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 📧 İletişim

Sorularınız için GitHub Issues kullanabilirsiniz.

---

**QuantTrade ile başarılı trading stratejileri geliştirin! 🚀**
