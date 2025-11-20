"""
QUANT-TRADE PREDICTION ENGINE — ALPHA MODEL (RANK-BASED)
--------------------------------------------------------
Bu sürüm:
- Hiçbir olasılık threshold'u kullanmaz
- Tamamen rank / percentile / top-N üzerinden sinyal üretir
- ALPHA modeline (%120 günde endeksi yenme ihtimali) göre çalışır

Sinyal mantığı:
    rank <= TOP_BUY_N              -> BUY
    rank >= (N - BOTTOM_SELL_N+1)  -> SELL
    aradakiler                     -> HOLD
"""

import warnings
warnings.filterwarnings("ignore")

import os
import glob
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from catboost import CatBoostClassifier

from sklearn.linear_model import LinearRegression
from sklearn.base import BaseEstimator, TransformerMixin
from typing import Dict


# ======================================================
#  SAME NEUTRALIZER CLASS (train ile birebir aynı isimde)
#  - Eğitimde: FeatureNeutralizer(market_ret).fit(X)
#  - Prediction'da: neutralizer.transform(X, market_ret=bugünkü_mkt)
# ======================================================

class FeatureNeutralizer(BaseEstimator, TransformerMixin):
    def __init__(self, market_ret=None):
        self.market_ret = market_ret
        self.models_: Dict[str, LinearRegression] = {}

    def fit(self, X, y=None):
        if self.market_ret is None:
            raise ValueError("market_ret must be provided for fitting.")
        mkt = self.market_ret.values.reshape(-1, 1)
        for col in X.columns:
            lr = LinearRegression()
            lr.fit(mkt, X[col].values)
            self.models_[col] = lr
        return self

    def transform(self, X, market_ret=None):
        """
        Eğitimdeki objeyi prediction'da da kullanmak için:
        - market_ret vermek ZORUNLU (bugünkü macro_bist100_roc_5d)
        - self.models_ eğitimden geliyor (joblib ile yüklendi)
        """
        if market_ret is None:
            raise ValueError("Prediction sırasında market_ret zorunludur.")

        Xn = X.copy()
        mkt = market_ret.values.reshape(-1, 1)

        for col in X.columns:
            lr = self.models_[col]
            pred = lr.predict(mkt)
            Xn[col] = X[col].values - pred

        return Xn


# ======================================================
# CONFIG
# ======================================================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha"
SIGNALS_DIR = "signals"

SYMBOL_COL = "symbol"
DATE_COL = "date"
MARKET_RET_COL = "macro_bist100_roc_5d"

# Rank tabanlı sinyal parametreleri
TOP_BUY_N = 15         # Günün en iyi 15 hissesi -> BUY
BOTTOM_SELL_N = 15     # Günün en kötü 15 hissesi -> SELL
TOP_N_PRINT = 20       # Terminal çıktısında gösterilecek satır sayısı


# ======================================================
# UTILS
# ======================================================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aranan dosya yok: {pattern}")
    return max(files, key=os.path.getmtime)


# ======================================================
# MAIN ENGINE
# ======================================================

def main():

    os.makedirs(SIGNALS_DIR, exist_ok=True)

    print("\n>> En son ALPHA modelini buluyorum...")
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha_*.pkl"))

    print(f"   Model      : {model_path}")
    print(f"   Neutralizer: {neutralizer_path}")

    # Model yükle
    model = CatBoostClassifier()
    model.load_model(model_path)

    # Neutralizer + feature list yükle
    meta = joblib.load(neutralizer_path)
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names = meta["features"]

    print("\n>> master_df.csv yükleniyor...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    latest_date = df[DATE_COL].max()
    df_today = df[df[DATE_COL] == latest_date].copy()

    print(f">> Tahmin tarihi: {latest_date.date()} | {len(df_today)} satır")

    if len(df_today) == 0:
        raise ValueError("Bugün için satır bulunamadı (master_df'i kontrol et).")

    # Feature matrix
    missing = [c for c in feature_names if c not in df_today.columns]
    if missing:
        raise ValueError(f"Eksik feature var (ilk 10): {missing[:10]}")

    X_today = df_today[feature_names].replace([np.inf, -np.inf], np.nan)
    X_today = X_today.fillna(X_today.median())

    # Bugünkü market getirisi (neutralization için)
    if MARKET_RET_COL not in df_today.columns:
        raise ValueError(f"{MARKET_RET_COL} kolonunu bulamadım master_df'te.")

    market_ret_today = df_today[MARKET_RET_COL].fillna(0.0)

    print(">> Feature neutralization uygulanıyor...")
    Xn_today = neutralizer.transform(X_today, market_ret=market_ret_today)

    print(">> Model skor üretiyor...")
    scores = model.predict_proba(Xn_today.values)[:, 1]

    # Sonuç df
    result = df_today[[SYMBOL_COL, DATE_COL]].copy()
    result["score"] = scores

    # Ranking / percentile
    result["rank"] = result["score"].rank(ascending=False).astype(int)
    result["percentile"] = result["score"].rank(pct=True)

    # Bucket = percentile * 10 (0–9)
    result["bucket"] = (result["percentile"] * 10).astype(int).clip(0, 9)

    # Başlangıçta hepsi HOLD
    result["signal"] = "HOLD"

    n = len(result)

    # BUY: en iyi TOP_BUY_N hisse
    result.loc[result["rank"] <= TOP_BUY_N, "signal"] = "BUY"

    # SELL: en kötü BOTTOM_SELL_N hisse
    # rank büyük → skor düşük
    sell_threshold = n - BOTTOM_SELL_N + 1
    result.loc[result["rank"] >= sell_threshold, "signal"] = "SELL"

    # Skora göre sırala
    result = result.sort_values("score", ascending=False).reset_index(drop=True)

    # Kaydet
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(
        SIGNALS_DIR,
        f"signals_alpha_{latest_date.strftime('%Y%m%d')}_{ts}.csv"
    )
    result.to_csv(out_path, index=False)

    print(f"\n>> Sinyaller kaydedildi: {out_path}")
    print(f">> BUY adedi   (TOP {TOP_BUY_N})    : {(result['signal']=='BUY').sum()}")
    print(f">> SELL adedi  (BOTTOM {BOTTOM_SELL_N}): {(result['signal']=='SELL').sum()}")
    print(f">> HOLD adedi                 : {(result['signal']=='HOLD').sum()}")

    print("\n>> En yüksek 20 skor:")
    print(result.head(TOP_N_PRINT).to_string(index=False))


# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    main()
