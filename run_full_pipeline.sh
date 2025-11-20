#!/bin/bash

# ============================================
# QUANTTRADE FULL DATA PIPELINE
# Tüm veri toplama, işleme ve feature engineering adımlarını çalıştırır
# ============================================

# Renkli output için
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Başlangıç zamanı
START_TIME=$(date +%s)

# Proje root directory
PROJECT_ROOT="/Users/furkanyilmaz/Desktop/QuantTrade"
cd "$PROJECT_ROOT" || exit 1

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}QUANTTRADE FULL PIPELINE BAŞLIYOR${NC}"
echo -e "${BLUE}Başlangıç: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}============================================${NC}\n"

# Hata kontrolü fonksiyonu
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ HATA: $1 başarısız!${NC}"
        echo -e "${YELLOW}Log dosyalarını kontrol edin.${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ $1 tamamlandı${NC}\n"
    fi
}

# ============================================
# ADIM 1: VERİ TOPLAMA (DATA SOURCES)
# ============================================

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}📥 ADIM 1/6: VERİ TOPLAMA${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "1.1. Makro ekonomik veriler (EVDS)..."
python3 src/quanttrade/data_sources/macro_downloader.py
check_error "Makro veri toplama"

echo "1.2. Hisse senedi fiyat verileri (OHLCV)..."
python3 src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py
check_error "OHLCV veri toplama"

echo "1.3. Mali tablo verileri..."
python3 src/quanttrade/data_sources/mali_tablo.py
check_error "Mali tablo veri toplama"

echo "1.4. Temettü verileri..."
python3 src/quanttrade/data_sources/temettü_scraper.py
check_error "Temettü veri toplama"

echo "1.5. Split ratio verileri..."
python3 src/quanttrade/data_sources/split_ratio.py
check_error "Split ratio veri toplama"

echo "1.6. KAP duyuruları..."
python3 src/quanttrade/data_sources/kap_announcement_scraper.py
check_error "KAP duyuru toplama"

# ============================================
# ADIM 2: VERİ TEMİZLEME (DATA PROCESSING)
# ============================================

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}🧹 ADIM 2/6: VERİ TEMİZLEME${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "2.1. OHLCV temizleme..."
python3 src/quanttrade/data_processing/ohlcv_cleaner.py
check_error "OHLCV temizleme"

echo "2.2. Mali tablo normalizasyonu..."
python3 src/quanttrade/data_processing/mali_tablo_normalizer.py
check_error "Mali tablo normalizasyon"

echo "2.3. Makro veri temizleme..."
python3 src/quanttrade/data_processing/macro_cleaner.py
check_error "Makro veri temizleme"

echo "2.4. Split veri temizleme..."
python3 src/quanttrade/data_processing/split_cleaner.py
check_error "Split veri temizleme"

echo "2.5. Temettü veri temizleme..."
python3 src/quanttrade/data_processing/dividend_cleaner.py
check_error "Temettü veri temizleme"

echo "2.6. Duyuru veri temizleme..."
python3 src/quanttrade/data_processing/announcement_cleaner.py
check_error "Duyuru veri temizleme"

# ============================================
# ADIM 3: FEATURE ENGINEERING
# ============================================

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}⚙️  ADIM 3/6: FEATURE ENGINEERING${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "3.1. Fiyat feature'ları..."
python3 src/quanttrade/feature_engineering/price_feature_engineer.py
check_error "Fiyat feature'ları"

echo "3.2. Fundamental feature'lar..."
python3 src/quanttrade/feature_engineering/fundamental_features.py
check_error "Fundamental feature'lar"

echo "3.3. Makro feature'lar..."
python3 src/quanttrade/feature_engineering/macro_features.py
check_error "Makro feature'lar"

echo "3.4. Master DataFrame oluşturma..."
python3 src/quanttrade/feature_engineering/master_builder.py
check_error "Master DataFrame"

# Master_df kontrolü
if [ -f "data/master/master_df.csv" ]; then
    FILE_SIZE=$(du -h data/master/master_df.csv | cut -f1)
    ROW_COUNT=$(wc -l < data/master/master_df.csv)
    echo -e "${GREEN}✅ master_df.csv hazır!${NC}"
    echo -e "   Boyut: ${FILE_SIZE}"
    echo -e "   Satır sayısı: ${ROW_COUNT}"
else
    echo -e "${RED}❌ master_df.csv oluşturulamadı!${NC}"
    exit 1
fi

# ============================================
# ADIM 4: MODEL EĞİTİMİ
# ============================================

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}🤖 ADIM 4/6: MODEL EĞİTİMİ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

cd src/quanttrade/models || exit 1
python3 train_model_pipeline.py
check_error "Model eğitimi"

# Model kontrolü
MODEL_COUNT=$(ls model_results/catboost_final_*.cbm 2>/dev/null | wc -l)
if [ "$MODEL_COUNT" -gt 0 ]; then
    LATEST_MODEL=$(ls -t model_results/catboost_final_*.cbm | head -1)
    echo -e "${GREEN}✅ Model kaydedildi: $LATEST_MODEL${NC}"
else
    echo -e "${RED}❌ Model oluşturulamadı!${NC}"
    exit 1
fi

# ============================================
# ADIM 5: TAHMİN ÜRETME
# ============================================

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}🎯 ADIM 5/6: TAHMİN ÜRETME${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

python3 prediction_engine.py
check_error "Tahmin üretme"

# Sinyal kontrolü
SIGNAL_COUNT=$(ls signals/signals_*.csv 2>/dev/null | wc -l)
if [ "$SIGNAL_COUNT" -gt 0 ]; then
    LATEST_SIGNAL=$(ls -t signals/signals_*.csv | head -1)
    echo -e "${GREEN}✅ Sinyaller oluşturuldu: $LATEST_SIGNAL${NC}"
else
    echo -e "${RED}❌ Sinyal dosyası oluşturulamadı!${NC}"
fi

# ============================================
# ADIM 6: BACKTEST
# ============================================

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}📈 ADIM 6/6: BACKTEST${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

python3 backtest_strategy.py
check_error "Backtest"

# Backtest kontrolü
BT_COUNT=$(ls backtest_results/backtest_*.csv 2>/dev/null | wc -l)
if [ "$BT_COUNT" -gt 0 ]; then
    LATEST_BT=$(ls -t backtest_results/backtest_*.csv | head -1)
    echo -e "${GREEN}✅ Backtest tamamlandı: $LATEST_BT${NC}"
else
    echo -e "${RED}❌ Backtest dosyası oluşturulamadı!${NC}"
fi

# ============================================
# ÖZET
# ============================================

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo -e "\n${BLUE}============================================${NC}"
echo -e "${GREEN}✅ TÜM PIPELINE BAŞARIYLA TAMAMLANDI!${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "Bitiş: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "Toplam süre: ${MINUTES}m ${SECONDS}s"
echo -e "\n${YELLOW}📊 ÇIKTI DOSYALARI:${NC}"
echo -e "   • Master DataFrame: data/master/master_df.csv"
echo -e "   • Eğitilmiş Model: src/quanttrade/models/model_results/"
echo -e "   • Sinyaller: src/quanttrade/models/signals/"
echo -e "   • Backtest: src/quanttrade/models/backtest_results/"
echo -e "\n${GREEN}Pipeline başarıyla tamamlandı! 🚀${NC}\n"
