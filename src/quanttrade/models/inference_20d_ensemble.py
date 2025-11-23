"""
QUANT-TRADE — ENSEMBLE INFERENCE (M2 STACKING, 20D)
Test split için base model + ensemble skorları hesaplar.
"""

import warnings
warnings.filterwarnings("ignore")

import os
import glob
from datetime import datetime

import numpy as np
import pandas as pd
import joblib

# train_20d_ensemble içindeki class ve sabitleri kullanıyoruz
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

SPLIT = "test"   # istersen "train", "valid" vs. yapabilirsin


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aranan dosya yok: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# MAIN
# ==========================

def main():
    print(">> Loading ensemble bundle...")
    bundle_path = get_latest(os.path.join(
        RESULTS_DIR, f"stacking_ensemble_alpha{HORIZON}d_*.pkl"
    ))
    print("  Bundle:", bundle_path)

    bundle = joblib.load(bundle_path)

    feature_names = bundle["features"]
    base_model_names = bundle["base_model_names"]
    base_models = bundle["base_models"]
    meta_model = bundle["meta_model"]
    sector_scaler: SectorStandardScaler = bundle["sector_scaler"]
    neutralizer: FeatureNeutralizer = bundle["neutralizer"]

    print(">> Loading data...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    if "dataset_split" not in df.columns:
        raise ValueError("dataset_split kolonu yok (train/valid/test ayrımı için gerekli).")

    df = df[df["dataset_split"] == SPLIT].reset_index(drop=True)

    print(f">> Split: {SPLIT}, satır sayısı: {len(df)}")

    # Feature matrix
    print(">> Building feature matrix...")
    X = df[feature_names].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    sector = df[SECTOR_COL].fillna("other").astype(str)

    # Sector z-score + neutralizer (aynı train pipeline)
    X_s = sector_scaler.transform(X, sector)
    X_n = neutralizer.transform(
        X_s,
        pd.DataFrame(index=df.index),  # faktör yoksa boş DF
        sector
    )

    # Base model skorları
    print(">> Predicting base model scores...")
    n_samples = len(df)
    n_models = len(base_model_names)
    base_scores = np.zeros((n_samples, n_models), dtype=float)

    for j, name in enumerate(base_model_names):
        model = base_models[name]
        print(f"  - {name} için tahmin alınıyor...")

        if name == "tabnet":
            X_input = X_n.values.astype(np.float32)
        else:
            X_input = X_n

        prob = model.predict_proba(X_input)[:, 1]
        base_scores[:, j] = prob

        df[f"score_{name}"] = prob

    # Meta model (ensemble skoru)
    print(">> Predicting ensemble (meta) scores...")
    meta_prob = meta_model.predict_proba(base_scores)[:, 1]
    df["score_ensemble"] = meta_prob

    # Çıktı
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(
        RESULTS_DIR,
        f"inference_alpha{HORIZON}d_ensemble_{SPLIT}_{ts}.csv"
    )

    # Önemli kolonlar + skorlar
    score_cols = [f"score_{name}" for name in base_model_names] + ["score_ensemble"]

    cols_to_save = []
    for c in [SYMBOL_COL, DATE_COL, "dataset_split"]:
        if c in df.columns:
            cols_to_save.append(c)

    # Label & future return'lar varsa onları da ekleyelim
    for c in df.columns:
        if c.startswith("future_return_") or c.startswith("market_future_return_") or c.startswith("y_"):
            cols_to_save.append(c)

    cols_to_save = list(dict.fromkeys(cols_to_save))  # uniq
    cols_to_save += score_cols

    df[cols_to_save].to_csv(out_path, index=False)
    print(">> Saved inference results to:", out_path)


if __name__ == "__main__":
    main()
