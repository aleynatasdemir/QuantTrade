from isyatirimhisse import fetch_financials
import pandas as pd
from pathlib import Path
import time
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ------------------------------------------------------------------
# 1) Hisse listesi (hardcoded - OHLCV'de kullandığımız aynı liste)
# ------------------------------------------------------------------
symbols = [
    "AKBNK", "ARCLK", "ASELS", "AVTUR", "BIMAS", "CCOLA", "DMSAS", "DOHOL", "EKGYO", "ENJSA",
    "ENKAI", "EREGL", "FROTO", "GARAN", "GLYHO", "GUBRF", "HALKB", "IPEKE", "ISCTR", "ISGYO",
    "KCHOL", "KOZAA", "KOZAL", "KRDMD", "MGROS", "MPARK", "NTHOL", "ODAS", "OYAKC", "PETKM",
    "PGSUS", "QUAGR", "SAHOL", "SASA", "SISE", "SKBNK", "SMART", "SNGYO", "SNPAM", "TAVHL",
    "TCELL", "THYAO", "TOASO", "TSPOR", "TTKOM", "TUPRS", "ULKER", "YKBNK", "ZOREN"
]

logging.info(f"{len(symbols)} adet sembol bulundu.")

# Proje kök dizinine göre ayarla (3 seviye yukarı: data_sources -> quanttrade -> src -> root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"

# fetch_financials parametrelerini tek yerde toplayalım
START_YEAR = "2022"
END_YEAR = "2026"
EXCHANGE = "USD"         # a.py'de USD kullanıyorsun
FINANCIAL_GROUP = "1"    # a.py'deki gibi (bilanço grubu)

no_data = []

# ------------------------------------------------------------------
# 2) Her hisse için İş Yatırım finansal verisini çek ve kaydet
# ------------------------------------------------------------------
for i, sym in enumerate(symbols, start=1):
    logging.info(f"[{i}/{len(symbols)}] {sym} için finansal veriler çekiliyor...")

    try:
        financial_data_output = fetch_financials(
            symbols=[sym],          # a.py'deki gibi LISTE veriyoruz
            start_year=START_YEAR,
            end_year=END_YEAR,
            exchange=EXCHANGE,
            financial_group=FINANCIAL_GROUP,
            save_to_excel=False,
        )
    except Exception as e:
        logging.error(f"{sym} için fetch_financials çağrısı hata verdi: {e}")
        no_data.append(sym)
        continue

    # a.py'deki gibi: bazen list, bazen direkt DataFrame dönebiliyor
    df_raw = None
    if isinstance(financial_data_output, list):
        if not financial_data_output:
            logging.warning(f"{sym}: boş liste döndü.")
        else:
            df_raw = financial_data_output[0]
    elif isinstance(financial_data_output, pd.DataFrame):
        df_raw = financial_data_output
    else:
        logging.error(
            f"{sym}: fetch_financials beklenmedik tip döndürdü: {type(financial_data_output)}"
        )

    if df_raw is None or df_raw.empty:
        logging.warning(f"{sym}: boş veya geçersiz DataFrame => kaydedilmeyecek.")
        no_data.append(sym)
        continue

    # --------------------------------------------------------------
    # Kaydetme: data/mali_tablo/{SYMBOL}.csv
    # --------------------------------------------------------------
    out_dir = BASE_DIR / "mali_tablo"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{sym}.csv"
    df_raw.to_csv(out_path, index=False, encoding="utf-8-sig")
    logging.info(f"{sym}: finansal veri kaydedildi -> {out_path}")

    # Siteyi boğmamak için küçük bekleme
    time.sleep(0.7)

# ------------------------------------------------------------------
# 3) Hiç veri çekilemeyen sembolleri logla
# ------------------------------------------------------------------
if no_data:
    nd_path = BASE_DIR / "mali_tablo_no_data_symbols.csv"
    pd.Series(no_data, name="symbol").to_csv(nd_path, index=False)
    logging.warning(f"Hiç finansal veri bulunamayan hisseler -> {nd_path}")
else:
    logging.info("Tüm semboller için en az bir miktar finansal veri bulundu.")
