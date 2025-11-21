"""
QUANT-TRADE — SLIDING WINDOW REALISTIC ALPHA BACKTESTER (M1 + M2)
(Train+Valid ile eğitilmiş model → sadece TEST üzerinde çalışır)

- M1: Yön tahmini (alpha 20d)
- M2: M1 sinyalinin güvenilirliği (meta-model)
- Her gün skor üretir (score_m1, score_m2, score_final).
- Her gün TOP_K hisse seçilir (M1+M2 sinyaline göre).
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
MARKET_RET_COL = "macro_bist100_roc_5d"

TOP_K = 5
MIN_STOCKS_PER_DAY = TOP_K

PRICE_COL = "price_close"
VOLUME_COL = "price_volume"
MIN_TURNOVER_TL = 5_000_000

COMMISSION_BPS = 5
SLIPPAGE_BPS = 5
ROUNDTRIP_COST = (COMMISSION_BPS + SLIPPAGE_BPS) / 10_000

RET_CAP = 0.5   # trade başına max ±%50

WATCHLIST: Optional[List[str]] = None
# WATCHLIST = ["KCHOL","SAHOL","THYAO", ...]


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aranan dosya yok: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# BACKTEST MAIN
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    # --------- MODELLERİ YÜKLE (M1 + NEUTRALIZER + M2) ----------
    print(">> Son M1 modelini buluyorum...")
    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha{HORIZON}d_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha{HORIZON}d_*.pkl"))

    print("   M1 Model       :", model_path)
    print("   Neutralizer    :", neutralizer_path)

    model_m1 = CatBoostClassifier()
    model_m1.load_model(model_path)

    meta_nz = joblib.load(neutralizer_path)
    sector_scaler: SectorStandardScaler = meta_nz["sector_scaler"]
    neutralizer: FeatureNeutralizer = meta_nz["neutralizer"]
    feature_names: List[str] = meta_nz["features"]

    # --- META MODEL (M2) ---
    print(">> Son M2 (meta) modelini buluyorum...")
    meta_model_path = get_latest(os.path.join(RESULTS_DIR, "meta_model_*.cbm"))
    meta_info_path = get_latest(os.path.join(RESULTS_DIR, "meta_info_*.pkl"))

    print("   M2 Model       :", meta_model_path)
    print("   M2 Info        :", meta_info_path)

    model_m2 = CatBoostClassifier()
    model_m2.load_model(meta_model_path)

    meta_info = joblib.load(meta_info_path)
    meta_features: List[str] = meta_info["meta_features"]
    m1_long_threshold: float = meta_info["m1_long_threshold"]
    m2_pos_threshold: float = meta_info["m2_pos_threshold"]

    # ==========================
    # DATA LOAD & FILTER
    # ==========================

    print(">> Veriyi yüklüyorum...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    if "dataset_split" not in df.columns:
        raise ValueError("master_df içinde dataset_split yok.")

    before_all = len(df)
    df = df[df["dataset_split"] == "test"].reset_index(drop=True)
    print(f">> TEST filtresi: {before_all} -> {len(df)} satır")

    before = len(df)
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL]).reset_index(drop=True)
    print(f">> FUT_RET + MARKET_FUT_RET dropna: {before} -> {len(df)} satır")

    if len(df) == 0:
        raise ValueError("Test döneminde future_return / market_future_return dolu satır kalmadı.")

    if WATCHLIST is not None:
        before = len(df)
        df = df[df[SYMBOL_COL].isin(WATCHLIST)].reset_index(drop=True)
        print(f">> WATCHLIST filtresi: {before} -> {len(df)} satır, "
              f"{df[SYMBOL_COL].nunique()} sembol")

    if PRICE_COL not in df.columns or VOLUME_COL not in df.columns:
        raise ValueError(f"Likidite filtresi için {PRICE_COL} ve {VOLUME_COL} kolonları gerekli.")

    df["turnover_tl"] = df[PRICE_COL].astype(float) * df[VOLUME_COL].astype(float)

    missing_feats = [f for f in feature_names if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Eksik feature(lar) var: {missing_feats[:10]} ...")

    X_all = df[feature_names].copy()
    X_all = X_all.replace([np.inf, -np.inf], np.nan)
    X_all = X_all.fillna(X_all.median())

    if "sector" not in df.columns:
        raise ValueError("master_df içinde 'sector' kolonu yok, backtest için gerekli.")
    sector_all = df["sector"].fillna("other").astype(str)

    print(">> Pre-processing (sector z-score + sector-neutralization)...")

    # 1) Sector Z-Score
    X_s = sector_scaler.transform(X_all, sector_all)

    # 2) Neutralization (train tarafındaki ile aynı mantık)
    factors_test = pd.DataFrame(index=df.index)
    X_all_n = neutralizer.transform(X_s, factors=factors_test, sector=sector_all)

    # ==========================
    # M1 SKORLARI
    # ==========================

    print(">> M1 MODEL SKOR ÜRETİYOR (TEST satırları)...")
    df["score_m1"] = model_m1.predict_proba(X_all_n.values)[:, 1]

    # ==========================
    # M2 SKORLARI (META MODEL)
    # ==========================

    print(">> M2 (META) FEATURE MATRİSİ OLUŞUYOR...")

    # meta_features içindeki kolonları test datasından çekiyoruz.
    # ÖZEL DURUM: "m1_oof_prob" meta feature'ının yerine "score_m1" kullanıyoruz.
    X_meta_list = []
    for col in meta_features:
        if col == "m1_oof_prob":
            X_meta_list.append(df["score_m1"])
        else:
            if col not in df.columns:
                raise ValueError(f"M2 için gereken feature test datasında yok: {col}")
            X_meta_list.append(df[col])

    X_meta = pd.concat(X_meta_list, axis=1)
    X_meta.columns = meta_features

    print(">> M2 MODEL SKOR ÜRETİYOR (TEST satırları)...")
    df["score_m2"] = model_m2.predict_proba(X_meta.values)[:, 1]

    # FINAL SCORE: M1 * M2
    df["score_final"] = df["score_m1"] * df["score_m2"]

    # Sinyal flag: M1 ve M2 eşiklerini geçenler
    df["signal_flag"] = (df["score_m1"] >= m1_long_threshold) & (df["score_m2"] >= m2_pos_threshold)

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

        # Sadece M1+M2 onaylı sinyaller
        candidates = liquid[liquid["signal_flag"]]

        if len(candidates) < MIN_STOCKS_PER_DAY:
            # Eğer yeterli sinyal yoksa bu günü trade etmiyoruz
            continue

        universe = candidates.sort_values("score_final", ascending=False)
        top = universe.head(TOP_K)

        gross_ret_raw = top[FUT_RET_COL]
        mkt_ret_raw = universe[MARKET_FUT_RET_COL]

        gross_ret = gross_ret_raw.clip(-RET_CAP, RET_CAP).mean()
        mkt_ret = mkt_ret_raw.clip(-RET_CAP, RET_CAP).mean()

        net_ret = gross_ret - ROUNDTRIP_COST
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
            "avg_score_m1": top["score_m1"].mean(),
            "avg_score_m2": top["score_m2"].mean(),
            "avg_score_final": top["score_final"].mean(),
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

    print("\n===== SLIDING WINDOW BACKTEST (TEST ONLY, M1 + M2) =====")
    print(f"Trade sayısı                  : {len(bt)}")
    print(f"Ortalama NET strateji getirisi: {mean_strat:.4f}")
    print(f"Ortalama endeks getirisi      : {mean_mkt:.4f}")
    print(f"Ortalama alpha                : {mean_alpha:.4f}")
    print(f"Sharpe (strateji)             : {sharpe_strat:.2f}")
    print(f"Sharpe (alpha)                : {sharpe_alpha:.2f}")
    print(f"Lift                          : {lift:.2f}")
    print(f"Nominal Hit Rate (TOP {TOP_K}): {bt['hit_rate_nominal'].mean():.2f}")
    print(f"Alpha>0 oranı                 : {bt['alpha_positive'].mean():.2f}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(BACKTEST_DIR, f"sliding_backtest_meta_{ts}.csv")
    png_path = os.path.join(BACKTEST_DIR, f"sliding_equity_meta_{ts}.png")

    bt.to_csv(csv_path, index=False)
    print("\nCSV kaydedildi:", csv_path)

    plt.figure(figsize=(10, 5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy (net, M1+M2)")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Market")
    plt.plot(bt["rebalance_date"], bt["alpha_equity"], label="Alpha")
    plt.title(f"SLIDING ALPHA BACKTEST (TOP {TOP_K} — {HORIZON}d — M1+M2)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return (1 = flat)")
    plt.yscale("log")
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path)
    plt.close()

    print("PNG kaydedildi:", png_path)
    print("\nSLIDING WINDOW BACKTEST (M1+M2) tamamlandı.")


if __name__ == "__main__":
    main()
