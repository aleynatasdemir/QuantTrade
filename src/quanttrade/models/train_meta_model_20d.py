"""
META MODEL TRAINING (M2)
Bağımsız dosya — M1'in OOF çıktılarıyla çalışır.
"""

import os
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from catboost import CatBoostClassifier
from sklearn.metrics import roc_auc_score
import glob
def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aranan dosya yok: {pattern}")
    return max(files, key=os.path.getmtime)
# ============================================================
# PATHS (DÜZELTİLMİŞ)
# ============================================================

DATA_PATH = "master_df.csv"   # M1 ile aynı dataset
RESULTS_DIR = "model_results_alpha_20d"  # M1 ile aynı klasör

# M1’in kaydettiği OOF npy dosyası
OOF_PATH = get_latest(os.path.join(RESULTS_DIR, f"oof_pred_m1_*.npy"))

os.makedirs(RESULTS_DIR, exist_ok=True)


# ============================================================
# CONFIG
# ============================================================

HORIZON = 20
ALPHA_COL = f"alpha_{HORIZON}d"

# M1'in AL adayı seçme seviyesi
M1_LONG_THRESHOLD = 0.55

# M2'nin AL onay eşiği (canlı kullanımda)
M2_POS_THRESHOLD = 0.50


# ============================================================
# LOAD DATA
# ============================================================

def load_data():
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)
    return df


# ============================================================
# BUILD META DATASET
# ============================================================

def build_meta_dataset(df, oof_pred):

    # 1) M1 ile AYNI FİLTRELEMEYİ UYGULA
    # M1: dropna(subset=[ALPHA_COL]) -> dropna(subset=["y_alpha"])
    df = df.dropna(subset=[ALPHA_COL]).reset_index(drop=True)
    
    # M1'deki target oluşturma
    q20 = df[ALPHA_COL].quantile(0.20)
    q80 = df[ALPHA_COL].quantile(0.80)
    df["y_alpha"] = np.where(
        df[ALPHA_COL] >= q80, 1,
        np.where(df[ALPHA_COL] <= q20, 0, np.nan)
    )
    df = df.dropna(subset=["y_alpha"]).reset_index(drop=True)
    
    # 2) Train+Valid subset
    df_tv = df[df["dataset_split"].isin(["train", "valid"])].reset_index(drop=True)

    # 3) OOF uzunluk kontrolü
    if len(oof_pred) != len(df_tv):
        raise ValueError(f"OOF length ({len(oof_pred)}) != train+valid length ({len(df_tv)})")

    # 4) OOF'i sadece train+valid'e ekle
    df_tv["m1_oof_prob"] = oof_pred

    # 5) M1 long candidate filtresi
    df_tv = df_tv[df_tv["m1_oof_prob"] >= M1_LONG_THRESHOLD].reset_index(drop=True)

    if df_tv.empty:
        raise ValueError("Meta dataset boş — M1 threshold çok yüksek olabilir.")

    # 6) META TARGET
    df_tv["y_meta"] = (df_tv[ALPHA_COL] > 0).astype(int)

    # 7) META FEATURES
    meta_cols = []
    for c in df_tv.columns:
        cl = c.lower()
        if any(kw in cl for kw in ["vol", "atr", "std", "var", "entropy", "regime"]):
            if not any(bad in cl for bad in ["future", "alpha_", "y_", "symbol", "date"]):
                meta_cols.append(c)

    # X_meta oluştur
    if meta_cols:
        X_meta = df_tv[meta_cols].copy()
    else:
        X_meta = pd.DataFrame(index=df_tv.index)

    # M1 prob daima feature
    X_meta["m1_oof_prob"] = df_tv["m1_oof_prob"] 

    y_meta = df_tv["y_meta"].values
    feature_list = list(X_meta.columns)

    return X_meta, y_meta, feature_list


# ============================================================
# TRAIN META MODEL
# ============================================================

def train_meta_model(X_meta, y_meta, feature_list):

    print(f">> META DATASET SIZE: {len(X_meta)} rows")

    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=4,
        learning_rate=0.05,
        iterations=600,
        verbose=False
    )

    model.fit(X_meta, y_meta)

    # Training AUC
    prob = model.predict_proba(X_meta)[:, 1]
    auc = roc_auc_score(y_meta, prob)

    print(f">> M2 TRAIN AUC: {auc:.3f}")

    # SAVE
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path = os.path.join(RESULTS_DIR, f"meta_model_{ts}.cbm")
    info_path = os.path.join(RESULTS_DIR, f"meta_info_{ts}.pkl")

    model.save_model(model_path)

    joblib.dump(
        {
            "meta_features": feature_list,
            "m1_long_threshold": M1_LONG_THRESHOLD,
            "m2_pos_threshold": M2_POS_THRESHOLD
        },
        info_path
    )

    print("\n>> Saved META MODEL:", model_path)
    print(">> Saved META INFO:", info_path)

    return model, auc


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n=== META MODEL TRAINING (M2) STARTED ===\n")

    df = load_data()

    # Load M1 OOF predictions
    print(">> Loading M1 OOF predictions:", OOF_PATH)
    oof_pred = np.load(OOF_PATH)

    # Build meta dataset
    print(">> Building meta dataset...")
    X_meta, y_meta, feature_names = build_meta_dataset(df, oof_pred)

    # Train meta model
    print(">> Training M2 model...")
    train_meta_model(X_meta, y_meta, feature_names)

    print("\n=== META MODEL TRAINING COMPLETED ✔️ ===\n")
