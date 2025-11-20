"""
QUANT-TRADE VIOP BACKTESTER (ALPHA + INDEX HEDGE, NON-OVERLAP)
--------------------------------------------------------------
- model_results_alpha içindeki SON CatBoost + Neutralizer'ı yükler
- master_df.csv üzerinden TÜM TARİH için skor üretir
- Her 120 günde bir:
    * ALPHA model skoruna göre TOP_K hisse LONG
    * XU100/XU030 endeksini temsilen market_future_return_120d üzerinden
      VİOP SHORT hedge uygular
- Overlap YOK (non-overlap); her trade 120 günlük bir periyodu kapsar
- Strateji getirisi:
      strategy_ret = mean(stock_future_return_120d) - HEDGE_RATIO * market_future_return_120d
- Sonuçlar backtest_results/ klasörüne yazılır
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
from typing import Dict


# ==========================
# FEATURE NEUTRALIZER CLASS
#  (ALPHA TRAIN’DE KULLANDIĞIN İLE AYNI İMZA)
# ==========================

class FeatureNeutralizer(BaseEstimator, TransformerMixin):
    """
    Eğitimde:
        neutralizer = FeatureNeutralizer(df[MARKET_RET_COL].fillna(0))
        Xn = neutralizer.fit_transform(X)

    Prediction / backtest’te:
        Xn_all = neutralizer.transform(X_all, market_ret_all)
    """
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
        if market_ret is None:
            raise ValueError("Prediction sırasında market_ret zorunludur.")

        Xn = X.copy()
        mkt = market_ret.values.reshape(-1, 1)

        for col in X.columns:
            lr = self.models_[col]
            pred = lr.predict(mkt)
            Xn[col] = X[col].values - pred

        return Xn


# ==========================
# CONFIG
# ==========================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha"
BACKTEST_DIR = "backtest_results"

SYMBOL_COL = "symbol"
DATE_COL = "date"
MARKET_RET_COL = "macro_bist100_roc_5d"

HORIZON = 120
FUT_RET_COL = f"future_return_{HORIZON}d"          # Hisse getirisi
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"  # Endeks getirisi (VİOP proxy)
ALPHA_COL = "alpha_120d"                           # future_return - market_future_return

TOP_K = 5          # Her rebalance’ta alınan hisse sayısı
MIN_STOCKS_PER_DAY = TOP_K

# Hedge oranı:
#   1.0 = full market-neutral (tam VİOP hedge)
#   0.5 = yarım hedge, vs.
HEDGE_RATIO = 1.0


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Dosya bulunamadı: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# MAIN
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Son ALPHA model ve neutralizer'ı buluyorum...")
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha_*.pkl"))

    print(f"   Model      : {model_path}")
    print(f"   Neutralizer: {neutralizer_path}")

    # Model
    model = CatBoostClassifier()
    model.load_model(model_path)

    # Neutralizer + feature list
    meta = joblib.load(neutralizer_path)
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names = meta["features"]

    print(">> Veriyi yüklüyorum...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # Gerekli kolon kontrolleri
    for col in [FUT_RET_COL, MARKET_FUT_RET_COL, ALPHA_COL, MARKET_RET_COL]:
        if col not in df.columns:
            raise ValueError(f"Gerekli kolon eksik: {col}")

    # Sadece future_return & market_future_return & alpha dolu satırlar
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL, ALPHA_COL]).reset_index(drop=True)

    # Feature kontrolü
    missing_feats = [f for f in feature_names if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Eksik feature(lar) var: {missing_feats[:10]} ...")

    # Feature matrix
    X_all = df[feature_names].copy()
    X_all = X_all.replace([np.inf, -np.inf], np.nan)
    X_all = X_all.fillna(X_all.median())

    market_ret_all = df[MARKET_RET_COL].fillna(0.0)

    print(">> Feature neutralization (tüm tarih)...")
    X_all_neutral = neutralizer.transform(X_all, market_ret=market_ret_all)

    print(">> Model skor üretiyor (tüm satırlar)...")
    df["score"] = model.predict_proba(X_all_neutral.values)[:, 1]

    # Tarihleri sırala (trading günleri)
    unique_dates = sorted(df[DATE_COL].unique())
    n_dates = len(unique_dates)

    print(f">> Toplam gün sayısı: {n_dates}")
    print(f">> Rebalance adımı (HORIZON): {HORIZON} gün")
    print(f">> TOP_K: {TOP_K}, HEDGE_RATIO (VİOP short): {HEDGE_RATIO}")

    records = []
    idx = 0

    while idx < n_dates:
        dt = unique_dates[idx]
        day_slice = df[df[DATE_COL] == dt]

        # Universe: ilgili günde trade edilebilir hisseler
        universe = day_slice.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL, ALPHA_COL])
        if len(universe) < MIN_STOCKS_PER_DAY:
            idx += 1
            continue

        # Skora göre sırala
        universe = universe.sort_values("score", ascending=False)

        top = universe.head(TOP_K)

        # Hisse getirisi (eşit ağırlıklı)
        stock_ret = top[FUT_RET_COL].mean()

        # Piyasa getirisi (endeks proxy)
        mkt_ret = universe[MARKET_FUT_RET_COL].mean()

        # Hisse ALPHA'sı (gerçekleşen)
        realized_alpha = stock_ret - mkt_ret

        # VİOP hedge PnL:
        #   VİOP short → strateji getirisine -HEDGE_RATIO * mkt_ret eklenir
        viop_pnl = -HEDGE_RATIO * mkt_ret

        # Toplam strateji getirisi
        strategy_ret = stock_ret + viop_pnl

        # Hedefimiz ALPHA yaratmak olduğundan,
        # aynı zamanda alpha bazlı hit rate'e de bakıyoruz:
        hit_rate_alpha = (top[ALPHA_COL] > 0).mean()

        records.append({
            "rebalance_date": dt,
            "n_universe": len(universe),
            "stock_ret": stock_ret,
            "market_ret": mkt_ret,
            "realized_alpha": realized_alpha,
            "hedge_ratio": HEDGE_RATIO,
            "viop_pnl": viop_pnl,
            "strategy_ret": strategy_ret,
            "hit_rate_alpha": hit_rate_alpha
        })

        # Bir sonraki trade: HORIZON gün sonrasına zıpla (overlap yok)
        idx += HORIZON

    if not records:
        raise ValueError("Hiç trade oluşmadı. Muhtemelen veri çok kısa ya da future_return/alpha kolonunda sorun var.")

    bt = pd.DataFrame(records).sort_values("rebalance_date").reset_index(drop=True)

    # Equity curve: trade bazlı, overlap yok
    bt["strategy_equity"] = (1 + bt["strategy_ret"]).cumprod()
    bt["stock_only_equity"] = (1 + bt["stock_ret"]).cumprod()
    bt["market_equity"] = (1 + bt["market_ret"]).cumprod()

    # Özet metrikler
    mean_strat = bt["strategy_ret"].mean()
    mean_stock = bt["stock_ret"].mean()
    mean_mkt = bt["market_ret"].mean()
    std_strat = bt["strategy_ret"].std()
    sharpe = mean_strat / (std_strat + 1e-9)

    lift_vs_market = (mean_strat / mean_mkt) if mean_mkt != 0 else np.nan
    lift_vs_stock_only = (mean_strat / mean_stock) if mean_stock != 0 else np.nan

    print("\n===== VIOP HEDGE BACKTEST ÖZET (ALPHA MODEL) =====")
    print(f"Trade sayısı                         : {len(bt)}")
    print(f"Ortalama hisse portföy getirisi      : {mean_stock:.4f}")
    print(f"Ortalama piyasa (endeks) getirisi    : {mean_mkt:.4f}")
    print(f"Ortalama strateji (hisse + VİOP)     : {mean_strat:.4f}")
    print(f"Sharpe (trade bazlı)                 : {sharpe:.2f}")
    print(f"Lift (strateji / piyasa)             : {lift_vs_market:.2f}")
    print(f"Lift (strateji / sadece hisse)       : {lift_vs_stock_only:.2f}")
    print(f"Ortalama ALPHA hit rate (TOP {TOP_K}): {bt['hit_rate_alpha'].mean():.2f}")
    print(f"HEDGE_RATIO                          : {HEDGE_RATIO}")

    # Kaydet
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(BACKTEST_DIR, f"backtest_viop_alpha_nonoverlap_{ts}.csv")
    bt.to_csv(out_csv, index=False)
    print(f"\nCSV kaydedildi: {out_csv}")

    # Equity curve plot
    plt.figure(figsize=(10, 5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy (Stock + VIOP hedge)")
    plt.plot(bt["rebalance_date"], bt["stock_only_equity"], label="Stock-only (no hedge)")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Market (index)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return (1 = flat)")
    plt.title(f"Equity Curve (TOP {TOP_K} / {HORIZON}d, VIOP hedge={HEDGE_RATIO})")
    plt.legend()
    plt.tight_layout()
    out_png = os.path.join(BACKTEST_DIR, f"equity_curve_viop_alpha_nonoverlap_{ts}.png")
    plt.savefig(out_png)
    plt.close()
    print(f"Equity curve PNG kaydedildi: {out_png}")

    print("\nVİOP hedge backtest tamamlandı.")


if __name__ == "__main__":
    main()
