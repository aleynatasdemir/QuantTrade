"""
QUANT-TRADE — ALPHA 20D MODEL (NO MACRO NEUTRALIZATION)
Leakage-Free + Purged Time Series CV
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import os
import joblib
from datetime import datetime
import matplotlib.pyplot as plt

from dataclasses import dataclass
from typing import Dict, Optional
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, roc_curve
from sklearn.model_selection import BaseCrossValidator
from sklearn.linear_model import LinearRegression
from catboost import CatBoostClassifier, Pool


# ============================
# CONFIG
# ============================
DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOL_COL = "symbol"
DATE_COL = "date"
SECTOR_COL = "sector"

HORIZON = 20
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"
ALPHA_COL = f"alpha_{HORIZON}d"

N_SPLITS = 5
PURGE_WINDOW = 10
EMBARGO_PCT = 0.05


# ============================================================
# PURGED TIME SERIES SPLIT
# ============================================================
@dataclass
class PurgedTimeSeriesSplit(BaseCrossValidator):
    n_splits: int
    purge_window: int
    embargo_pct: float

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, X, y=None, groups=None):
        n = len(X)
        idx = np.arange(n)

        fold_sizes = np.full(self.n_splits, n // self.n_splits)
        fold_sizes[: n % self.n_splits] += 1

        start = 0
        for fold_size in fold_sizes:
            test_start = start
            test_end = start + fold_size
            start = test_end

            train_mask = np.ones(n, dtype=bool)
            purge_start = max(0, test_start - self.purge_window)
            train_mask[purge_start:test_end] = False

            embargo = int(n * self.embargo_pct)
            emb_start = test_end
            emb_end = min(n, test_end + embargo)
            train_mask[emb_start:emb_end] = False

            yield idx[train_mask], idx[test_start:test_end]


# ============================================================
# SECTOR STANDARD SCALER  (BUNU KORUYORUZ)
# ============================================================
class SectorStandardScaler(BaseEstimator, TransformerMixin):

    def __init__(self):
        self.stats_ = {}

    def fit(self, X: pd.DataFrame, sector: pd.Series):
        sector = sector.astype(str)
        self.stats_ = {}
        for sec in sector.unique():
            mask = (sector == sec)
            X_sec = X.loc[mask]
            mean = X_sec.mean()
            std = X_sec.std(ddof=0).replace(0, 1.0)
            self.stats_[sec] = {"mean": mean, "std": std}
        return self

    def transform(self, X: pd.DataFrame, sector: pd.Series):
        sector = sector.astype(str)
        Xs = X.copy()
        for sec, st in self.stats_.items():
            mask = (sector == sec)
            if mask.any():
                Xs.loc[mask] = (X.loc[mask] - st["mean"]) / st["std"]
        return Xs


# ============================================================
# FEATURE SELECTION
# ============================================================
def select_features(df):

    drop_cols = {
        c for c in df.columns
        if "future_" in c or (c.startswith("y_") and c != "y_triple_20d")
    }
    drop_cols |= {
        SYMBOL_COL, DATE_COL, "y_triple_20d",
        ALPHA_COL, FUT_RET_COL, MARKET_FUT_RET_COL, SECTOR_COL
    }
    drop_cols |= {
        "price_open", "price_high", "price_low", "price_adj_close"
    }

    features = [
        c for c in df.columns
        if c not in drop_cols and pd.api.types.is_numeric_dtype(df[c])
    ]

    X = df[features].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    return X, features


# ============================================================
# METRICS + ROC
# ============================================================
def save_metrics_and_plots(y_true, y_prob, fold_auc_list):

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    auc = roc_auc_score(y_true, y_prob)
    y_pred = (y_prob >= 0.5).astype(int)

    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)

    metrics_df = pd.DataFrame({
        "AUC": [auc],
        "Precision": [precision],
        "Recall": [recall],
        "F1": [f1],
        "Fold_AUCs": [fold_auc_list]
    })
    metrics_df.to_csv(f"{RESULTS_DIR}/metrics_{ts}.csv", index=False)

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    plt.plot([0, 1], [0, 1], "k--")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/roc_curve_{ts}.png")
    plt.close()


# ============================================================
# TRAIN PIPELINE
# ============================================================
def run_pipeline():

    print(">> Loading data...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    df = df.dropna(subset=["y_triple_20d"]).reset_index(drop=True)
    df["y_triple_20d"] = df["y_triple_20d"].astype(int)

    df_tv = df[df["dataset_split"].isin(["train", "valid"])].reset_index(drop=True)

    print(">> Selecting features...")
    X, feature_names = select_features(df_tv)
    y = df_tv["y_triple_20d"].reset_index(drop=True)

    sector_all = df_tv[SECTOR_COL].fillna("other").astype(str).reset_index(drop=True)

    print(">> Purged CV training...")
    cv = PurgedTimeSeriesSplit(N_SPLITS, PURGE_WINDOW, EMBARGO_PCT)

    oof_pred = np.zeros(len(df_tv))
    fold_aucs = []

    for fold, (tr, te) in enumerate(cv.split(X), 1):

        X_tr = X.iloc[tr].reset_index(drop=True)
        X_te = X.iloc[te].reset_index(drop=True)

        sec_tr = sector_all.iloc[tr].reset_index(drop=True)
        sec_te = sector_all.iloc[te].reset_index(drop=True)

        # === SADECE SEKTÖR Z-SCORE ===
        sec_scaler = SectorStandardScaler()
        sec_scaler.fit(X_tr, sec_tr)

        X_tr_s = sec_scaler.transform(X_tr, sec_tr)
        X_te_s = sec_scaler.transform(X_te, sec_te)

        model = CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            depth=6,
            learning_rate=0.05,
            iterations=700,
            verbose=False
        )
        model.fit(X_tr_s, y.iloc[tr])

        prob = model.predict_proba(X_te_s)[:, 1]
        oof_pred[te] = prob

        auc = roc_auc_score(y.iloc[te], prob)
        fold_aucs.append(auc)

        print(f"Fold {fold}: AUC={auc:.3f}")

    print("\n>> Saving metrics...")
    save_metrics_and_plots(y, oof_pred, fold_aucs)

    print("\n>> Training FINAL MODEL...")
    scaler_final = SectorStandardScaler()
    scaler_final.fit(X, sector_all)
    X_final = scaler_final.transform(X, sector_all)

    final_model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=6,
        learning_rate=0.05,
        iterations=700,
        verbose=False
    )
    final_model.fit(X_final, y)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n>> Saving FINAL MODEL...")
    final_model.save_model(f"{RESULTS_DIR}/catboost_alpha20d_{ts}.cbm")
    joblib.dump(
        {
            "sector_scaler": scaler_final,
            "features": feature_names
        },
        f"{RESULTS_DIR}/neutralizer_alpha20d_{ts}.pkl"
    )

    print("\n✨ TRAINING COMPLETED — NO MACRO NEUTRALIZATION ✔️")


if __name__ == "__main__":
    run_pipeline()
