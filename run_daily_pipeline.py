"""
QuantTrade - Günlük Data Pipeline Orchestrator

Çalıştırma (proje kökünden):
    python run_daily_pipeline.py

Sıra:
1) data_sources  (ham veri çekme)
2) data_processing (temizleme / normalize)
3) feature_engineering (feature + master_df)
Her step sonrası output dosyaları otomatik kontrol edilir.
"""

import subprocess
import sys
import logging
import os
from pathlib import Path
from typing import List, Dict, Callable, Optional

import glob
import pandas as pd

# -------------------------------------------------------------------
# PYTHONPATH'e src ekle (quanttrade modülü için)
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
os.environ["PYTHONPATH"] = str(SRC_PATH) + os.pathsep + os.environ.get("PYTHONPATH", "")

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("daily_pipeline")

PYTHON = sys.executable  # aktif env'deki python

# -------------------------------------------------------------------
# Yardımcı Fonksiyonlar (Validasyon)
# -------------------------------------------------------------------


def _glob_files(pattern: str) -> List[Path]:
    """Glob pattern ile dosya bulur, yoksa hata fırlatır."""
    files = [Path(p) for p in glob.glob(pattern)]
    if not files:
        raise RuntimeError(f"Pattern için dosya bulunamadı: {pattern}")
    return files


def _validate_csv_files_exist_and_not_empty(pattern: str, step_name: str) -> List[Path]:
    files = _glob_files(pattern)
    for f in files:
        if f.stat().st_size == 0:
            raise RuntimeError(f"[{step_name}] Boş dosya: {f}")
    logger.info("[%s] %d dosya bulundu (pattern: %s)", step_name, len(files), pattern)
    return files


def _validate_parquet_file(path: str, step_name: str) -> Path:
    f = Path(path)
    if not f.exists():
        raise RuntimeError(f"[{step_name}] Parquet dosyası yok: {f}")
    if f.stat().st_size == 0:
        raise RuntimeError(f"[{step_name}] Parquet dosyası boş: {f}")
    logger.info("[%s] Parquet dosyası OK: %s", step_name, f)
    return f


def _check_required_columns(
    df: pd.DataFrame,
    required_cols: List[str],
    file: Path,
    step_name: str,
):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise RuntimeError(
            f"[{step_name}] {file} içinde eksik kolon(lar): {missing}"
        )


def validate_macro_raw():
    """data/raw/macro/evds_macro_daily.csv var mı, boş mu, temel kolonlar var mı?"""
    step_name = "RAW_MACRO"
    files = _validate_csv_files_exist_and_not_empty(
        "data/raw/macro/evds_macro_daily.csv", step_name
    )
    for f in files:
        df = pd.read_csv(f)
        _check_required_columns(
            df,
            ["date"],  # burada sadece date'i garanti edelim
            f,
            step_name,
        )
    logger.info("[%s] Makro RAW kontrolü OK.", step_name)


def validate_ohlcv_raw():
    """data/raw/ohlcv/*_ohlcv_isyatirim.csv kontrolü."""
    step_name = "RAW_OHLCV"
    files = _validate_csv_files_exist_and_not_empty(
        "data/raw/ohlcv/*_ohlcv_isyatirim.csv", step_name
    )
    # Çok dosya olacağı için sadece ilk birkaç dosyada temel kolonlara bakalım
    sample_files = files[:5]
    for f in sample_files:
        df = pd.read_csv(f)
        required = ["date", "open", "high", "low", "close", "volume"]
        # hamda isimler türkçe olabilir, bu sadece kabaca check; eksikse log verelim ama pipeline'ı durdurmayalım
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.warning(
                "[%s] UYARI: %s içinde beklenen ham kolonlar yok: %s",
                step_name,
                f,
                missing,
            )
    logger.info("[%s] OHLCV RAW kontrolü (dosya/boş) OK.", step_name)


def validate_mali_tablo_raw():
    step_name = "RAW_MALI_TABLO"
    _validate_csv_files_exist_and_not_empty(
        "data/raw/mali_tablo/*.csv", step_name
    )
    logger.info("[%s] Mali tablo RAW dosyaları OK.", step_name)


def validate_bist_financials_raw():
    step_name = "RAW_BIST_FINANCIALS"
    _validate_csv_files_exist_and_not_empty(
        "data/raw/financials/*_financials_all_periods.csv", step_name
    )
    logger.info("[%s] BIST financials RAW dosyaları OK.", step_name)


def validate_announcements_raw():
    step_name = "RAW_ANNOUNCEMENTS"
    _validate_csv_files_exist_and_not_empty(
        "data/raw/announcements/*_announcements.csv", step_name
    )
    logger.info("[%s] Announcements RAW dosyaları OK.", step_name)


def validate_split_raw():
    step_name = "RAW_SPLIT"
    _validate_csv_files_exist_and_not_empty(
        "data/raw/split_ratio/*_split.csv", step_name
    )
    logger.info("[%s] Split RAW dosyaları OK.", step_name)


def validate_dividends_raw():
    step_name = "RAW_DIVIDEND"
    _validate_csv_files_exist_and_not_empty(
        "data/raw/dividend/*_dividends.csv", step_name
    )
    logger.info("[%s] Temettü RAW dosyaları OK.", step_name)


# ------------------- DATA PROCESSING VALIDATION ---------------------


def validate_ohlcv_clean():
    step_name = "PROC_OHLCV"
    files = _validate_csv_files_exist_and_not_empty(
        "data/processed/ohlcv/*_ohlcv_clean.csv", step_name
    )
    required = ["date", "open", "high", "low", "close", "volume", "symbol"]
    for f in files[:10]:  # ilk 10 dosyada kolon check
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] OHLCV clean kontrolü OK.", step_name)


def validate_macro_clean():
    step_name = "PROC_MACRO"
    files = _validate_csv_files_exist_and_not_empty(
        "data/processed/macro/evds_macro_daily_clean.csv", step_name
    )
    required = ["date", "usd_try", "eur_try", "cpi", "bist100"]
    for f in files:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Macro clean kontrolü OK.", step_name)


def validate_mali_tablo_processed():
    step_name = "PROC_MALI_TABLO"
    files = _validate_csv_files_exist_and_not_empty(
        "data/processed/mali_tablo/*_financials_long.csv", step_name
    )
    required = [
        "symbol",
        "period",
        "item_code",
        "item_name_tr",
        "item_name_en",
        "value",
    ]
    for f in files[:10]:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Mali tablo long format kontrolü OK.", step_name)


def validate_dividends_clean():
    step_name = "PROC_DIVIDEND"
    files = _validate_csv_files_exist_and_not_empty(
        "data/processed/dividend/*_dividends_clean.csv", step_name
    )
    required = [
        "symbol",
        "ex_date",
        "dividend_yield_pct",
        "dividend_per_share",
        "gross_pct",
        "net_pct",
        "total_dividend_tl",
        "payout_ratio_pct",
    ]
    for f in files[:10]:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Temettü clean kontrolü OK.", step_name)


def validate_split_clean():
    step_name = "PROC_SPLIT"
    files = _validate_csv_files_exist_and_not_empty(
        "data/processed/split/*_split_clean.csv", step_name
    )
    required = [
        "symbol",
        "split_date",
        "split_factor",
        "cumulative_split_factor",
    ]
    for f in files[:10]:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Split clean kontrolü OK.", step_name)


def validate_announcements_clean():
    step_name = "PROC_ANNOUNCEMENTS"
    files = _validate_csv_files_exist_and_not_empty(
        "data/processed/announcements/*_announcements_clean.csv", step_name
    )
    required = [
        "symbol",
        "announcement_date",
        "ruleType",
        "summary",
        "url",
    ]
    for f in files[:10]:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Announcements clean kontrolü OK.", step_name)


# ------------------ FEATURE ENGINEERING VALIDATION ------------------


def validate_price_features():
    step_name = "FE_PRICE"
    files = _validate_csv_files_exist_and_not_empty(
        "data/features/price/*_price_features.csv", step_name
    )
    required = [
        "symbol",
        "date",
        "adj_close",
        "adj_open",
        "adj_high",
        "adj_low",
        "return_1d",
        "return_5d",
        "return_20d",
        "vol_20d",
        "vol_60d",
        "sma_20",
        "sma_50",
        "sma_200",
        "rsi_14",
        "macd",
        "macd_signal",
        "is_dividend_day",
        "distance_from_ma200",
        "future_return_10d",
        "future_return_20d",
        "y_10d_triclass",
        "y_20d_triclass",
        "y_30d_triclass",
        "y_60d_triclass",
        "y_90d_triclass",
        "y_120d_triclass",
    ]
    for f in files[:10]:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Price features kontrolü OK.", step_name)


def validate_fundamental_features():
    step_name = "FE_FUNDAMENTAL"
    files = _validate_csv_files_exist_and_not_empty(
        "data/features/fundamental/*_fundamental_period_features.csv", step_name
    )
    required = [
        "symbol",
        "period",
        "announcement_date",
        "net_profit",
        "net_sales",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "roe",
        "roa",
        "net_margin",
        "debt_to_equity",
        "revenue_growth_yoy",
        "profit_growth_yoy",
    ]
    for f in files[:10]:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Fundamental features kontrolü OK.", step_name)


def validate_macro_features():
    step_name = "FE_MACRO"
    files = _validate_csv_files_exist_and_not_empty(
        "data/features/macro/macro_features_daily.csv", step_name
    )
    required = [
        "date",
        "usd_try",
        "usdtry_roc_1d",
        "usdtry_roc_5d",
        "usdtry_roc_20d",
        "usdtry_ma200",
        "usdtry_distance_ma200",
        "usdtry_vol_20d",
        "usdtry_vol_60d",
        "usdtry_vol_regime",
        "eur_try",
        "eurtry_roc_1d",
        "eurtry_roc_5d",
        "eurtry_roc_20d",
        "bist100",
        "bist100_roc_1d",
        "bist100_roc_5d",
        "bist100_roc_20d",
        "bist100_roc_60d",
        "bist100_ma200",
        "bist100_distance_ma200",
    ]
    for f in files:
        df = pd.read_csv(f)
        _check_required_columns(df, required, f, step_name)
    logger.info("[%s] Macro features kontrolü OK.", step_name)


def validate_master_df():
    step_name = "MASTER_DF"
    f = _validate_parquet_file("data/master/master_df.parquet", step_name)
    df = pd.read_parquet(f)
    if df.empty:
        raise RuntimeError(f"[{step_name}] master_df.parquet boş!")
    required = [
        "symbol",
        "date",
        "price_adj_close",
        "price_return_1d",
        "price_return_5d",
        "price_return_20d",
        "price_vol_20d",
        "price_sma_200",
        "price_distance_from_ma200",
        "price_rsi_14",
        "price_macd",
        "macro_usd_try",
        "macro_usdtry_roc_1d",
        "macro_bist100",
        "fund_net_profit",
        "fund_net_sales",
        "fund_roe",
        "fund_debt_to_equity",
        "future_return_10d",
        "y_10d_triclass",
        "y_20d_triclass",
        "y_30d_triclass",
        "y_60d_triclass",
        "y_90d_triclass",
        "y_120d_triclass",
    ]
    _check_required_columns(df, required, f, step_name)
    logger.info("[%s] master_df kontrolü OK. Satır sayısı: %d", step_name, len(df))


# -------------------------------------------------------------------
# Orchestrator
# -------------------------------------------------------------------

StepValidator = Optional[Callable[[], None]]


def run_step(name: str, cmd: List[str], validator: StepValidator = None):
    logger.info("▶ STEP: %s", name)
    logger.info("   Komut: %s", " ".join(cmd))

    # PYTHONPATH'i subprocess'e aktar
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_PATH) + os.pathsep + env.get("PYTHONPATH", "")
    
    result = subprocess.run(cmd, text=True, env=env, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"[{name}] script hata ile döndü (exit={result.returncode})")

    logger.info("[✓] %s script bitti.", name)

    if validator:
        logger.info("   → %s için validasyon başlıyor...", name)
        validator()
        logger.info("   → %s validasyon OK.", name)


def main():
    """
    Tüm pipeline'ı sırasıyla çalıştırır.
    Bu script'i proje kökünden çalıştır:
        python run_daily_pipeline.py
    """
    steps: List[Dict] = [
        # ---------------- DATA SOURCES ----------------
         
        {
            "name": "MACRO_DOWNLOADER",
            "cmd": [PYTHON, "src/quanttrade/data_sources/macro_downloader.py"],
            "validator": validate_macro_raw,
        },
        {
            "name": "ISYATIRIM_OHLCV_DOWNLOADER",
            "cmd": [PYTHON, "src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py"],
            "validator": validate_ohlcv_raw,
        },
        {
            "name": "MALI_TABLO_RAW",
            "cmd": [PYTHON, "src/quanttrade/data_sources/mali_tablo.py"],
            "validator": validate_mali_tablo_raw,
        },
        {
            "name": "BIST_DATA_COLLECTOR_ALL_PERIODS",
            "cmd": [PYTHON, "src/quanttrade/data_sources/bist_data_collector_all_periods.py"],
            "validator": validate_bist_financials_raw,
        },
        {
            "name": "KAP_ANNOUNCEMENT_SCRAPER",
            "cmd": [PYTHON, "src/quanttrade/data_sources/deneme.py"],
            "validator": validate_announcements_raw,
        },
        {
            "name": "SPLIT_RATIO_SCRAPER",
            "cmd": [PYTHON, "src/quanttrade/data_sources/split_ratio.py"],
            "validator": validate_split_raw,
        },
        {
            "name": "TEMETTU_SCRAPER",
            "cmd": [PYTHON, "src/quanttrade/data_sources/temettü_scraper.py"],
            "validator": validate_dividends_raw,
        },

        # --------------- DATA PROCESSING ---------------
        {
            "name": "OHLCV_CLEANER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/ohlcv_cleaner.py"],
            "validator": validate_ohlcv_clean,
        },
        {
            "name": "MACRO_CLEANER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/macro_cleaner.py"],
            "validator": validate_macro_clean,
        },
        {
            "name": "MALI_TABLO_CONVERTER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/mali_tablo_converter.py"],
            "validator": None,  # output'u normalizer zaten kontrol edecek
        },
        {
            "name": "MALI_TABLO_NORMALIZER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/mali_tablo_normalizer.py"],
            "validator": validate_mali_tablo_processed,
        },
        {
            "name": "DIVIDEND_CLEANER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/dividend_cleaner.py"],
            "validator": validate_dividends_clean,
        },
        {
            "name": "SPLIT_CLEANER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/split_cleaner.py"],
            "validator": validate_split_clean,
        },
        {
            "name": "ANNOUNCEMENT_CLEANER",
            "cmd": [PYTHON, "src/quanttrade/data_processing/announcement_cleaner.py"],
            "validator": validate_announcements_clean,
        },

        # ------------ FEATURE ENGINEERING --------------
        {
            "name": "PRICE_FEATURE_ENGINEER",
            "cmd": [PYTHON, "src/quanttrade/feature_engineering/price_feature_engineer.py"],
            "validator": validate_price_features,
        },
        {
            "name": "FUNDAMENTAL_FEATURE_ENGINEER",
            "cmd": [PYTHON, "src/quanttrade/feature_engineering/fundamental_features.py"],
            "validator": validate_fundamental_features,
        },
        {
            "name": "MACRO_FEATURE_ENGINEER",
            "cmd": [PYTHON, "src/quanttrade/feature_engineering/macro_features.py"],
            "validator": validate_macro_features,
        },
        {
            "name": "MASTER_BUILDER",
            "cmd": [PYTHON, "src/quanttrade/feature_engineering/master_builder.py"],
            "validator": validate_master_df,
        },
        {
            "name": "PARQUET_TO_CSV",
            "cmd": [PYTHON, "src/quanttrade/data_sources/parquet_to_csv.py"],
            
        },
    ]

    try:
        for step in steps:
            run_step(step["name"], step["cmd"], step.get("validator"))
        logger.info("🎉 Tüm günlük pipeline başarıyla tamamlandı.")
    except Exception as e:
        logger.error("💥 Pipeline HATASI: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()