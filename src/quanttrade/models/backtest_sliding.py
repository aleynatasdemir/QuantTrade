"""
QUANT-TRADE — SLIDING WINDOW REALISTIC ALPHA BACKTESTER
(Train+Valid ile eğitilmiş model → sadece TEST üzerinde çalışır)

- Her gün skor üretir.
- Her gün TOP_K hisse seçilir.
- Realized horizon getiri: future_return_{HORIZON}d
- Benchmark: market_future_return_{HORIZON}d
- Alpha = net_strategy_ret - market_ret
- Transaction cost + slippage uygulanır.
- Likidite filtresi + opsiyonel watchlist
- Sliding Window: overlap VAR (her gün yeni trade)
"""

import warnings
warnings.filterwarnings("ignore")

import os
import glob
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from catboost import CatBoostClassifier

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LinearRegression
from typing import Dict, Optional, List


# ==========================
# CONFIG
# ==========================

DATA_PATH = "master_df.csv"

# ← horizon'a göre klasörleri değiştir
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_alpha_20d"

SYMBOL_COL = "symbol"
DATE_COL = "date"

HORIZON = 20   # ← sadece burayı değiştirirsin (10 / 20 / 30 / 60 / 90 / 120 ...)
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"
MARKET_RET_COL = "macro_bist100_roc_5d"

TOP_K = 5
MIN_STOCKS_PER_DAY = TOP_K

PRICE_COL = "price_close"
VOLUME_COL = "price_volume"
MIN_TURNOVER_TL = 5_000_000

COMMISSION_BPS = 5
SLIPPAGE_BPS = 5
ROUNDTRIP_COST = (COMMISSION_BPS + SLIPPAGE_BPS) / 10_000

# Aşırı uç işlemleri kırpmak için (örn: +%50 / -%50)
RET_CAP = 0.5   # trade başına max ±%50; istersen 0.3, 0.2 yap

WATCHLIST: Optional[List[str]] = None
# WATCHLIST = ["KCHOL","SAHOL","THYAO", ...]


# ==========================
# NEUTRALIZER
# ==========================

class FeatureNeutralizer(BaseEstimator, TransformerMixin):
    def __init__(self, market_ret: Optional[pd.Series] = None):
        if market_ret is not None:
            self.market_ret = market_ret.values.reshape(-1, 1)
        else:
            self.market_ret = None
        self.models_: Dict[str, LinearRegression] = {}

    def fit(self, X, y=None):
        if self.market_ret is None:
            raise ValueError("market_ret None, cannot fit.")
        for col in X.columns:
            lr = LinearRegression()
            lr.fit(self.market_ret, X[col].values)
            self.models_[col] = lr
        return self

    def transform(self, X, market_ret=None):
        if market_ret is not None:
            mr = market_ret.values.reshape(-1, 1)
        else:
            mr = self.market_ret

        if mr is None:
            raise ValueError("No market_ret available for transform().")

        Xn = X.copy()
        for col in X.columns:
            lr = self.models_[col]
            pred = lr.predict(mr)
            Xn[col] = X[col] - pred
        return Xn


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Dosya bulunamadı: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# BACKTEST MAIN
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Son modeli buluyorum...")
    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha{HORIZON}d_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha{HORIZON}d_*.pkl"))

    print("   Model       :", model_path)
    print("   Neutralizer :", neutralizer_path)

    # Model
    model = CatBoostClassifier()
    model.load_model(model_path)

    # Neutralizer + feature list
    meta = joblib.load(neutralizer_path)
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names: List[str] = meta["features"]

    print(">> Veriyi yüklüyorum...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    if "dataset_split" not in df.columns:
        raise ValueError("master_df içinde dataset_split yok.")

    before_all = len(df)
    df = df[df["dataset_split"] == "test"].reset_index(drop=True)
    print(f">> TEST filtresi: {before_all} -> {len(df)} satır")

    # Future return ve market future return dolu satırlar
    before = len(df)
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL]).reset_index(drop=True)
    print(f">> FUT_RET + MARKET_FUT_RET dropna: {before} -> {len(df)} satır")

    if len(df) == 0:
        raise ValueError("Test döneminde future_return / market_future_return dolu satır kalmadı.")

    # WATCHLIST opsiyonel
    if WATCHLIST is not None:
        before = len(df)
        df = df[df[SYMBOL_COL].isin(WATCHLIST)].reset_index(drop=True)
        print(f">> WATCHLIST filtresi: {before} -> {len(df)} satır, "
              f"{df[SYMBOL_COL].nunique()} sembol")

    # Likidite için turnover
    if PRICE_COL not in df.columns or VOLUME_COL not in df.columns:
        raise ValueError(f"Likidite filtresi için {PRICE_COL} ve {VOLUME_COL} kolonları gerekli.")

    df["turnover_tl"] = df[PRICE_COL].astype(float) * df[VOLUME_COL].astype(float)

    # Feature kontrolü
    missing_feats = [f for f in feature_names if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Eksik feature(lar) var: {missing_feats[:10]} ...")

    # Feature matrix
    X_all = df[feature_names].copy()
    X_all = X_all.replace([np.inf, -np.inf], np.nan)
    X_all = X_all.fillna(X_all.median())

    market_ret_all = df[MARKET_RET_COL].fillna(0.0)

    print(">> Neutralization (sadece TEST dönemi)...")
    X_all_n = neutralizer.transform(X_all, market_ret=market_ret_all)

    print(">> MODEL SKOR ÜRETİYOR (TEST satırları)...")
    df["score"] = model.predict_proba(X_all_n.values)[:, 1]

    unique_dates = sorted(df[DATE_COL].unique())
    print(f">> Sliding window backtest başlıyor ({len(unique_dates)} gün)")

    records = []

    # ==============================
    # SLIDING WINDOW LOOP
    # ==============================
    for dt in unique_dates:
        day_slice = df[df[DATE_COL] == dt]

        # Likidite filtresi
        liquid = day_slice[day_slice["turnover_tl"] >= MIN_TURNOVER_TL]
        if len(liquid) < MIN_STOCKS_PER_DAY:
            continue

        # Skor sıralaması
        universe = liquid.sort_values("score", ascending=False)
        top = universe.head(TOP_K)

        # Return cap uygula (uçları kırp)
        gross_ret_raw = top[FUT_RET_COL]
        mkt_ret_raw = universe[MARKET_FUT_RET_COL]

        gross_ret = gross_ret_raw.clip(-RET_CAP, RET_CAP).mean()
        mkt_ret = mkt_ret_raw.clip(-RET_CAP, RET_CAP).mean()

        # Transaction cost + slippage (round-trip)
        net_ret = gross_ret - ROUNDTRIP_COST

        # Alpha
        alpha_ret = net_ret - mkt_ret

        hit_rate = (gross_ret_raw > 0).mean()

        records.append({
            "rebalance_date": dt,
            "n_universe": len(universe),
            "strategy_gross_ret": gross_ret,
            "strategy_net_ret": net_ret,
            "market_ret": mkt_ret,
            "alpha_ret": alpha_ret,
            "hit_rate_nominal": hit_rate,
            "alpha_positive": float(alpha_ret > 0),
        })

    if not records:
        raise ValueError("Hiç trade oluşmadı. Muhtemelen filtreler çok sıkı veya test dönemi çok kısa.")

    bt = pd.DataFrame(records).sort_values("rebalance_date").reset_index(drop=True)

    # ==============================
    # EQUITY CURVES
    # ==============================
    bt["strategy_equity"] = (1 + bt["strategy_net_ret"]).cumprod()
    bt["market_equity"] = (1 + bt["market_ret"]).cumprod()
    bt["alpha_equity"] = (1 + bt["alpha_ret"]).cumprod()

    # ==============================
    # METRICS
    # ==============================
    mean_strat = bt["strategy_net_ret"].mean()
    mean_mkt = bt["market_ret"].mean()
    mean_alpha = bt["alpha_ret"].mean()

    std_strat = bt["strategy_net_ret"].std()
    std_alpha = bt["alpha_ret"].std()

    sharpe_strat = mean_strat / (std_strat + 1e-9)
    sharpe_alpha = mean_alpha / (std_alpha + 1e-9)
    lift = mean_strat / mean_mkt if mean_mkt != 0 else np.nan

    print("\n===== SLIDING WINDOW BACKTEST (TEST ONLY) =====")
    print(f"Trade sayısı                  : {len(bt)}")
    print(f"Ortalama NET strateji getirisi: {mean_strat:.4f}")
    print(f"Ortalama endeks getirisi      : {mean_mkt:.4f}")
    print(f"Ortalama alpha                : {mean_alpha:.4f}")
    print(f"Sharpe (strateji)             : {sharpe_strat:.2f}")
    print(f"Sharpe (alpha)                : {sharpe_alpha:.2f}")
    print(f"Lift                          : {lift:.2f}")
    print(f"Nominal Hit Rate (TOP {TOP_K}): {bt['hit_rate_nominal'].mean():.2f}")
    print(f"Alpha>0 oranı                 : {bt['alpha_positive'].mean():.2f}")

    # ==============================
    # SAVE
    # ==============================
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(BACKTEST_DIR, f"sliding_backtest_{ts}.csv")
    png_path = os.path.join(BACKTEST_DIR, f"sliding_equity_{ts}.png")

    bt.to_csv(csv_path, index=False)
    print("\nCSV kaydedildi:", csv_path)

    # Grafik (log scale, patlamayı engeller)
    plt.figure(figsize=(10, 5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy (net)")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Market")
    plt.plot(bt["rebalance_date"], bt["alpha_equity"], label="Alpha")
    plt.title(f"SLIDING ALPHA BACKTEST (TOP {TOP_K} — {HORIZON}d)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return (1 = flat)")
    plt.yscale("log")  # ← önemli
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path)
    plt.close()

    print("PNG kaydedildi:", png_path)
    print("\nSLIDING WINDOW BACKTEST tamamlandı.")


if __name__ == "__main__":
    main()
