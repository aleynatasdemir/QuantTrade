"""
QUANT-TRADE — SLIDING WINDOW ALPHA BACKTEST (M1 ONLY)
+ Inverse Volatility Weighting
+ 3% Stop-Loss (daha sıkı)
+ Market Regime Filter (bist100 MA200, soft + hard)
+ Trade Log (hangi gün hangi hisse, hangi ağırlıkla alındı)
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

from typing import List
from train_model_20d import SectorStandardScaler, FeatureNeutralizer

# ==========================
# CONFIG
# ==========================

DATA_PATH = "master_df.csv"

RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_alpha_20d"

SYMBOL_COL = "symbol"
DATE_COL = "date"

HORIZON = 20
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"

TOP_K = 5
MIN_TURNOVER_TL = 5_000_000
RET_CAP = 0.5

STOP_LOSS = -0.03

REGIME_FILTER_COL = "macro_bist100_distance_ma200"
ROUNDTRIP_COST = 0.001
PRICE_COL = "price_close"
VOLUME_COL = "price_volume"

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
# BACKTEST
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    # ------------------- M1 MODEL ---------------------
    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha{HORIZON}d_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha{HORIZON}d_*.pkl"))

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(neutralizer_path)
    sector_scaler: SectorStandardScaler = meta["sector_scaler"]
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names: List[str] = meta["features"]

    # ------------------- DATA -------------------------
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    df = df[df["dataset_split"] == "test"].reset_index(drop=True)
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL]).reset_index(drop=True)

    df["turnover_tl"] = df[PRICE_COL] * df[VOLUME_COL]
    df = df[df["turnover_tl"] >= MIN_TURNOVER_TL].reset_index(drop=True)

    # Preprocessing
    X = df[feature_names].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    sector = df["sector"].astype(str)

    X_s = sector_scaler.transform(X, sector)
    X_n = neutralizer.transform(X_s, pd.DataFrame(index=df.index), sector)

    # ------------------- M1 SCORE ---------------------
    df["score_m1"] = model.predict_proba(X_n)[:, 1]

    # Günlük döngü
    dates = sorted(df[DATE_COL].unique())
    bt_records = []
    trade_records = []        # <<< YENİ: trade log

    print(f">> Sliding Window başlıyor ({len(dates)} gün)...")
    regime_warned = False

    for dt in dates:
        day = df[df[DATE_COL] == dt]

        # En yüksek skorlu TOP_K
        day = day.sort_values("score_m1", ascending=False).head(TOP_K)
        if len(day) < TOP_K:
            continue

        # 1) INVERSE VOLATILITY WEIGHTING
        if "price_vol_20d" not in day.columns:
            if not regime_warned:
                print("⚠ price_vol_20d yok → equal weight kullanıyorum.")
                regime_warned = True
            vol = np.ones(len(day))
        else:
            vol = day["price_vol_20d"].clip(lower=1e-6).values

        w = 1.0 / vol
        w = w / w.sum()

        # 2) STOP LOSS (–3%)
        raw_fwd = day[FUT_RET_COL].clip(-RET_CAP, RET_CAP).values
        fwd = np.maximum(raw_fwd, STOP_LOSS)

        # 3) MARKET REGIME FILTER
        risk_multiplier = 1.0
        regime_value = np.nan
        if REGIME_FILTER_COL in day.columns:
            regime_value = day[REGIME_FILTER_COL].iloc[0]

            if regime_value <= HARD_BEAR_THRESHOLD:
                # Sert ayı → hiç trade alma, trade log da yazma
                continue
            elif regime_value < 0:
                risk_multiplier = 0.5
        else:
            if not regime_warned:
                print("⚠ MA200 rejim kolonu yok, filtre devre dışı.")
                regime_warned = True

        # 4) PORTFÖY NET GETİRİ
        gross_ret = np.sum(w * fwd) * risk_multiplier
        net_ret = gross_ret - ROUNDTRIP_COST * risk_multiplier

        mkt_ret = day[MARKET_FUT_RET_COL].clip(-RET_CAP, RET_CAP).mean()
        alpha_ret = net_ret - mkt_ret

        # ----- GÜNLÜK ÖZET KAYDI -----
        bt_records.append({
            "rebalance_date": dt,
            "strategy_net_ret": net_ret,
            "market_ret": mkt_ret,
            "alpha_ret": alpha_ret,
            "weighted_hit_rate": float(np.sum(w * (fwd > 0))),
            "regime_value": regime_value,
            "risk_multiplier": risk_multiplier,
        })

        # ----- TRADE LOG (HİSSE BAZINDA) -----
        for i, row in day.reset_index(drop=True).iterrows():
            trade_records.append({
                "rebalance_date": dt,
                "symbol": row[SYMBOL_COL],
                "score_m1": row["score_m1"],
                "weight": w[i] * risk_multiplier,           # fiili portföy payı
                "raw_future_ret": raw_fwd[i],               # stop öncesi (clipped)
                "future_ret_after_sl": fwd[i],              # stop-loss sonrası
                "contrib_to_portfolio": w[i] * fwd[i] * risk_multiplier,
                "regime_value": regime_value,
                "risk_multiplier": risk_multiplier,
            })

    # ======================
    # DATAFRAME'LER
    # ======================
    bt = pd.DataFrame(bt_records).sort_values("rebalance_date").reset_index(drop=True)
    trades = pd.DataFrame(trade_records).sort_values(["rebalance_date", "symbol"]).reset_index(drop=True)

    bt["strategy_equity"] = (1 + bt["strategy_net_ret"]).cumprod()
    bt["market_equity"] = (1 + bt["market_ret"]).cumprod()
    bt["alpha_equity"] = (1 + bt["alpha_ret"]).cumprod()

    # METRİKLER
    mean_strat = bt["strategy_net_ret"].mean()
    std_strat = bt["strategy_net_ret"].std() + 1e-9
    mean_alpha = bt["alpha_ret"].mean()
    std_alpha = bt["alpha_ret"].std() + 1e-9

    sharpe_strat = mean_strat / std_strat
    sharpe_alpha = mean_alpha / std_alpha

    print("\n===== SLIDING WINDOW BACKTEST (M1 ONLY — WEIGHTED+STOPLOSS+REGIME) =====")
    print(f"Trade günleri: {len(bt)}")
    print(f"Ortalama net getiri: {mean_strat:.4f}")
    print(f"Sharpe (strateji): {sharpe_strat:.2f}")
    print(f"Sharpe (alpha): {sharpe_alpha:.2f}")
    print(f"Alpha>0 oranı: {(bt['alpha_ret'] > 0).mean():.2f}")
    print(f"Ağırlıklı Hit Rate ort.: {bt['weighted_hit_rate'].mean():.2f}")
    print(f"Toplam trade satırı: {len(trades)}")

    # SAVE
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv_bt = f"{BACKTEST_DIR}/sliding_weighted_{ts}.csv"
    out_csv_trades = f"{BACKTEST_DIR}/sliding_trades_{ts}.csv"
    out_png = f"{BACKTEST_DIR}/sliding_weighted_{ts}.png"

    bt.to_csv(out_csv_bt, index=False)
    trades.to_csv(out_csv_trades, index=False)

    print("Backtest CSV:", out_csv_bt)
    print("Trades   CSV:", out_csv_trades)

    plt.figure(figsize=(10, 5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Market")
    plt.plot(bt["rebalance_date"], bt["alpha_equity"], label="Alpha")
    plt.yscale("log")
    plt.legend()
    plt.title("SLIDING BACKTEST — WEIGHTED + STOPLOSS + REGIME FILTER")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()
    print("PNG:", out_png)


if __name__ == "__main__":
    main()
