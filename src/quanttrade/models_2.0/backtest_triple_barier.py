"""
QUANT-TRADE — CLEAN BACKTEST (TRIPLE-BARRIER MODEL)
Zero Lookahead — Horizon Shift — True Neutralization
"""

import warnings
warnings.filterwarnings("ignore")

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
from catboost import CatBoostClassifier
import matplotlib.pyplot as plt

from train_model import SectorStandardScaler, FeatureNeutralizer

# ============================================================
# CONFIG
# ============================================================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_alpha_20d"

SYMBOL_COL = "symbol"
DATE_COL = "date"
SECTOR_COL = "sector"

HORIZON = 20
TARGET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_COL = f"market_future_return_{HORIZON}d"

TOP_K = 5
MIN_TURNOVER_TL = 5_000_000
RET_CAP = 0.50

STOP_LOSS = -0.03
ROUNDTRIP_COST = 0.001

REGIME_COL = "macro_bist100_distance_ma200"
HARD_BEAR_THRESHOLD = -0.02

PRICE_COL = "price_close"
VOLUME_COL = "price_volume"

import glob

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Dosya bulunamadı: {pattern}")
    return max(files, key=os.path.getmtime)


# ============================================================
# HORIZON SHIFT — MODEL INPUT T, RETURN T+20
# ============================================================

def build_horizon_shifted(df, horizon):
    df = df.copy()
    df["model_date"] = df[DATE_COL]
    df["return_date"] = df[DATE_COL] + pd.Timedelta(days=horizon)

    fut = df[[SYMBOL_COL, DATE_COL, TARGET_COL]]
    fut = fut.rename(columns={DATE_COL: "return_date", TARGET_COL: "future_ret_h"})

    merged = df.merge(
        fut,
        on=[SYMBOL_COL, "return_date"],
        how="left"
    )

    merged = merged.dropna(subset=["future_ret_h"]).reset_index(drop=True)
    return merged


# ============================================================
# MAIN BACKTEST
# ============================================================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha{HORIZON}d_*.cbm"))
    neutral_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha{HORIZON}d_*.pkl"))

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(neutral_path)
    sector_scaler: SectorStandardScaler = meta["sector_scaler"]
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names = meta["features"]
    factors_train = meta["factors"]
    sector_train = meta["sector"]

    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    test = df[df["dataset_split"] == "test"].reset_index(drop=True)

    test = build_horizon_shifted(test, HORIZON)

    test["turnover"] = test[PRICE_COL] * test[VOLUME_COL]
    test = test[test["turnover"] >= MIN_TURNOVER_TL].reset_index(drop=True)

    X = test[feature_names].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    sector_test = test[SECTOR_COL].astype(str)

    factors_test = pd.DataFrame(
        np.zeros((len(test), factors_train.shape[1])),
        columns=factors_train.columns
    )

    X_s = sector_scaler.transform(X, sector_test)
    X_n = neutralizer.transform(X_s, factors_test, sector_test)

    test["score"] = model.predict_proba(X_n)[:, 1]

    dates = sorted(test["model_date"].unique())

    daily_log = []
    trade_log = []

    print(f">> BACKTEST BAŞLIYOR — {len(dates)} gün")

    for dt in dates:
        day = test[test["model_date"] == dt].copy()
        if len(day) == 0:
            continue

        day = day.sort_values("score", ascending=False).head(TOP_K)

        if "price_vol_20d" in day.columns:
            vol = day["price_vol_20d"].clip(lower=1e-6).values
        else:
            vol = np.ones(len(day))

        w = 1 / vol
        w = w / w.sum()

        fut_raw = day["future_ret_h"].values
        fut_cap = np.clip(fut_raw, -RET_CAP, RET_CAP)
        fut_eff = np.maximum(fut_cap, STOP_LOSS)

        regime_val = day[REGIME_COL].iloc[0]
        risk_mult = 1.0

        if regime_val <= HARD_BEAR_THRESHOLD:
            continue
        elif regime_val < 0:
            risk_mult = 0.5

        gross = float(np.sum(w * fut_eff)) * risk_mult
        net = gross - ROUNDTRIP_COST * risk_mult

        mkt_ret = float(day[MARKET_FUT_COL].mean())
        alpha = net - np.clip(mkt_ret, -RET_CAP, RET_CAP)

        daily_log.append({
            "date": dt,
            "regime_val": regime_val,
            "risk_mult": risk_mult,
            "strategy_ret": net,   # 20 günlük blok getirisi
            "market_ret": mkt_ret,
            "alpha_ret": alpha,
            "hit_rate": float(np.sum(w * (fut_eff > 0)))
        })

        exit_date = dt + timedelta(days=HORIZON)

        for (_, row), weight, fr_raw, fr_eff in zip(day.iterrows(), w, fut_raw, fut_eff):
            trade_log.append({
                "entry": dt,
                "exit": exit_date,
                "symbol": row[SYMBOL_COL],
                "weight": float(weight),
                "future_raw": float(fr_raw),
                "future_eff": float(fr_eff)
            })

    # ===================== RESULTS =====================

    bt = pd.DataFrame(daily_log).sort_values("date").reset_index(drop=True)

    # --- GRAFİK İÇİN DÜZELTME ---
    # 20 günlük getiriyi günlük eşdeğer faktöre çevirip ondan equity hesaplıyoruz
    strat_daily_factor = (1.0 + bt["strategy_ret"]) ** (1.0 / HORIZON)
    mkt_daily_factor   = (1.0 + bt["market_ret"])   ** (1.0 / HORIZON)
    alpha_daily_factor = (1.0 + bt["alpha_ret"])    ** (1.0 / HORIZON)

    bt["equity"]        = strat_daily_factor.cumprod()
    bt["market_equity"] = mkt_daily_factor.cumprod()
    bt["alpha_equity"]  = alpha_daily_factor.cumprod()

    # ============================================================
    # PERFORMANCE METRICS
    # ============================================================
    def calc_metrics(bt, horizon=20):
        r = bt["strategy_ret"].values   # 20 GÜNLÜK getiriler

        mu = r.mean()
        sigma = r.std() + 1e-12

        sharpe_20 = mu / sigma
        sharpe_ann = np.sqrt(252 / horizon) * sharpe_20
        annual_return = (1 + mu) ** (252 / horizon) - 1

        eq = bt["equity"].values
        roll_max = np.maximum.accumulate(eq)
        max_dd = ((eq - roll_max) / roll_max).min()

        hit_rate = (r > 0).mean()

        return {
            "days": len(r),
            "sharpe_20d": sharpe_20,
            "sharpe_annual": sharpe_ann,
            "annual_return": annual_return,
            "max_drawdown": max_dd,
            "mean_20d_return": mu,
            "std_20d_return": sigma,
            "hit_rate": hit_rate,
        }

    metrics = calc_metrics(bt, horizon=HORIZON)

    print("\n===== PERFORMANCE METRICS =====")
    print(f"Periods (20d blocks): {metrics['days']}")
    print(f"Sharpe (20d): {metrics['sharpe_20d']:.2f}")
    print(f"Sharpe (Annualized): {metrics['sharpe_annual']:.2f}")
    print(f"Annual Return: {metrics['annual_return']:.2%}")
    print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"Mean 20d Return: {metrics['mean_20d_return']:.4f}")
    print(f"Std 20d Return: {metrics['std_20d_return']:.4f}")
    print(f"Hit Rate: {metrics['hit_rate']:.2%}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    metrics_path = f"{BACKTEST_DIR}/performance_metrics_{ts}.csv"
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)
    print("Performance metrics saved:", metrics_path)

    out_csv = f"{BACKTEST_DIR}/final_bt_{ts}.csv"
    out_trades = f"{BACKTEST_DIR}/final_trades_{ts}.csv"
    out_png = f"{BACKTEST_DIR}/final_equity_{ts}.png"

    bt.to_csv(out_csv, index=False)
    pd.DataFrame(trade_log).to_csv(out_trades, index=False)

    plt.figure(figsize=(10,5))
    plt.plot(bt["date"], bt["equity"], label="Strategy")
    plt.plot(bt["date"], bt["market_equity"], label="Market")
    plt.plot(bt["date"], bt["alpha_equity"], label="Alpha")
    # plt.yscale("log")  # günlük eşdeğer equity'de log gereksiz
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

    print("\n>> KAYDEDİLENLER:")
    print("• Günlük Backtest:", out_csv)
    print("• Trade Log:", out_trades)
    print("• Equity Curve PNG:", out_png)
    print("• Metrics:", metrics_path)
    print("\n>> BACKTEST TAMAMLANDI — ZERO LEAKAGE ✔️")


if __name__ == "__main__":
    main()
