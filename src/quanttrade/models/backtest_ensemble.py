"""
QUANT-TRADE — SLIDING WINDOW ALPHA BACKTEST (M2 ENSEMBLE)
+ Inverse Volatility Weighting
+ 3% Stop-Loss (daha sıkı)
+ Market Regime Filter (bist100 MA200, soft + hard)
+ Ensemble score (M2: stacking, meta LR)
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

from typing import List

# Train script'ten sabitler ve class'lar
from train_20d_ensemble import (
    SectorStandardScaler,
    FeatureNeutralizer,
    SYMBOL_COL,
    DATE_COL,
    SECTOR_COL,
    HORIZON,
    DATA_PATH,
    RESULTS_DIR,
)

# ==========================
# CONFIG
# ==========================

BACKTEST_DIR = "backtest_results_alpha_20d_ensemble"

FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"

TOP_K = 5
MIN_TURNOVER_TL = 5_000_000
RET_CAP = 0.5

# STOP-LOSS: daha sıkı (–3%)
STOP_LOSS = -0.03

# Rejim filtresi: distance_from_ma200 tarzı kolon
REGIME_FILTER_COL = "macro_bist100_distance_ma200"
ROUNDTRIP_COST = 0.001            # %0.1 total roundtrip
PRICE_COL = "price_close"
VOLUME_COL = "price_volume"

# Sert ayı eşiği (ör: -0.02 = -%2 MA200 altı)
HARD_BEAR_THRESHOLD = -0.02


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aranan dosya yok: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# BACKTEST (ENSEMBLE)
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    # ------------------- ENSEMBLE BUNDLE ---------------------
    bundle_path = get_latest(os.path.join(
        RESULTS_DIR, f"stacking_ensemble_alpha{HORIZON}d_*.pkl"
    ))
    print(">> Loading ensemble bundle:", bundle_path)

    bundle = joblib.load(bundle_path)

    feature_names: List[str] = bundle["features"]
    base_model_names: List[str] = bundle["base_model_names"]
    base_models = bundle["base_models"]
    meta_model = bundle["meta_model"]
    sector_scaler: SectorStandardScaler = bundle["sector_scaler"]
    neutralizer: FeatureNeutralizer = bundle["neutralizer"]

    # ------------------- DATA -------------------------
    print(">> Loading data...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    if "dataset_split" not in df.columns:
        raise ValueError("dataset_split kolonu yok (train/valid/test ayrımı için gerekli).")

    df = df[df["dataset_split"] == "test"].reset_index(drop=True)
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL]).reset_index(drop=True)

    # Likidite filtresi
    df["turnover_tl"] = df[PRICE_COL] * df[VOLUME_COL]
    df = df[df["turnover_tl"] >= MIN_TURNOVER_TL].reset_index(drop=True)

    print(f">> Test satırı (likidite filtresi sonrası): {len(df)}")

    # ------------------- FEATURE PIPELINE ---------------------
    print(">> Building ensemble feature matrix...")
    X = df[feature_names].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    sector = df[SECTOR_COL].fillna("other").astype(str)

    X_s = sector_scaler.transform(X, sector)
    X_n = neutralizer.transform(
        X_s,
        pd.DataFrame(index=df.index),  # faktörler yoksa boş DF
        sector
    )

    # ------------------- BASE + META SKOR ---------------------
    print(">> Predicting base model scores (test)...")

    n_samples = len(df)
    n_models = len(base_model_names)
    base_scores = np.zeros((n_samples, n_models), dtype=float)

    for j, name in enumerate(base_model_names):
        model = base_models[name]
        print(f"  - {name} inference...")

        if name == "tabnet":
            X_input = X_n.values.astype(np.float32)
        else:
            X_input = X_n

        prob = model.predict_proba(X_input)[:, 1]
        base_scores[:, j] = prob
        df[f"score_{name}"] = prob

    print(">> Predicting meta (ensemble) scores...")
    df["score_m2"] = meta_model.predict_proba(base_scores)[:, 1]

    # ------------------- SLIDING WINDOW BACKTEST --------------
    dates = sorted(df[DATE_COL].unique())
    records = []

    print(f">> Sliding Window başlıyor ({len(dates)} gün)...")
    regime_warned = False
    vol_warned = False
    regime_col_warned = False

    for dt in dates:
        day = df[df[DATE_COL] == dt]

        # Ensemble skora göre en iyi TOP_K hisse
        day = day.sort_values("score_m2", ascending=False).head(TOP_K)
        if len(day) < TOP_K:
            continue

        # 1) INVERSE VOLATILITY WEIGHTING
        if "price_vol_20d" not in day.columns:
            if not vol_warned:
                print("⚠ price_vol_20d yok → equal weight kullanıyorum.")
                vol_warned = True
            vol = np.ones(len(day))
        else:
            vol = day["price_vol_20d"].clip(lower=1e-6).values

        w = 1.0 / vol
        w = w / w.sum()

        # 2) STOP LOSS (daha sıkı: -3%)
        fwd = day[FUT_RET_COL].clip(-RET_CAP, RET_CAP).values
        fwd = np.maximum(fwd, STOP_LOSS)

        # 3) MARKET REGIME FILTER (MA200)
        risk_multiplier = 1.0
        if REGIME_FILTER_COL in day.columns:
            reg_val = day[REGIME_FILTER_COL].iloc[0]

            # Sert ayı: MA200'ün %2'den fazla altında → hiç trade alma
            if reg_val <= HARD_BEAR_THRESHOLD:
                # bu günü tamamen pas geçiyoruz
                continue

            # Hafif ayı: MA200 biraz altında → pozisyonu yarıya indir
            elif reg_val < 0:
                risk_multiplier = 0.5

        else:
            if not regime_col_warned:
                print("⚠ MA200 rejim kolonu yok, filtre devre dışı.")
                regime_col_warned = True

        # 4) NET RETURN
        gross_ret = np.sum(w * fwd) * risk_multiplier
        net_ret = gross_ret - ROUNDTRIP_COST * risk_multiplier

        # 5) MARKET RETURN
        mkt_ret = day[MARKET_FUT_RET_COL].clip(-RET_CAP, RET_CAP).mean()

        alpha_ret = net_ret - mkt_ret

        records.append({
            "rebalance_date": dt,
            "strategy_net_ret": net_ret,
            "market_ret": mkt_ret,
            "alpha_ret": alpha_ret,
            "weighted_hit_rate": float(np.sum(w * (fwd > 0))),
        })

    bt = pd.DataFrame(records).sort_values("rebalance_date").reset_index(drop=True)

    if bt.empty:
        print("⚠ Hiç trade günü oluşmamış (filtreler çok sıkı olabilir).")
        return

    bt["strategy_equity"] = (1 + bt["strategy_net_ret"]).cumprod()
    bt["market_equity"] = (1 + bt["market_ret"]).cumprod()
    bt["alpha_equity"] = (1 + bt["alpha_ret"]).cumprod()

    # METRICS
    mean_strat = bt["strategy_net_ret"].mean()
    std_strat = bt["strategy_net_ret"].std() + 1e-9
    mean_alpha = bt["alpha_ret"].mean()
    std_alpha = bt["alpha_ret"].std() + 1e-9

    sharpe_strat = mean_strat / std_strat
    sharpe_alpha = mean_alpha / std_alpha

    print("\n===== SLIDING WINDOW BACKTEST (M2 ENSEMBLE — WEIGHTED+STOPLOSS+REGIME) =====")
    print(f"Trade günleri: {len(bt)}")
    print(f"Ortalama net getiri: {mean_strat:.4f}")
    print(f"Sharpe (strateji): {sharpe_strat:.2f}")
    print(f"Sharpe (alpha): {sharpe_alpha:.2f}")
    print(f"Alpha>0 oranı: {(bt['alpha_ret'] > 0).mean():.2f}")
    print(f"Ağırlıklı Hit Rate ort.: {bt['weighted_hit_rate'].mean():.2f}")

    # SAVE
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(BACKTEST_DIR, f"sliding_ensemble_{ts}.csv")
    out_png = os.path.join(BACKTEST_DIR, f"sliding_ensemble_{ts}.png")

    bt.to_csv(out_csv, index=False)

    plt.figure(figsize=(10, 5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy (Ensemble)")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Market")
    plt.plot(bt["rebalance_date"], bt["alpha_equity"], label="Alpha")
    plt.yscale("log")
    plt.legend()
    plt.title("SLIDING BACKTEST — ENSEMBLE (M2) + WEIGHTED + STOPLOSS + REGIME FILTER")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

    print("CSV:", out_csv)
    print("PNG:", out_png)


if __name__ == "__main__":
    main()
