"""
QUANT-TRADE FULL PIPELINE — ALPHA MODEL (FINAL VERSION)
-------------------------------------------------------
Bu model nominal getiriyi değil ALPHA'yı öğrenir:
    alpha_120d = (future_return_120d - market_future_return_120d)

Amaç:
- 120 günde endeksi YENECEK hisseleri tahmin etmek.
- Enflasyondan bağımsız, gerçek edge üretmek.
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
from typing import Dict

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, roc_curve
from sklearn.model_selection import BaseCrossValidator
from sklearn.linear_model import LinearRegression

from catboost import CatBoostClassifier, Pool


# ============================================================
# CONFIG
# ============================================================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha"
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOL_COL = "symbol"
DATE_COL = "date"
PRICE_COL = "price_adj_close"

HORIZON = 60
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"
FUT_RET_COL = f"future_return_{HORIZON}d"
ALPHA_COL = "alpha_120d"

MARKET_RET_COL = "macro_bist100_roc_5d"

# CV parameters
N_SPLITS = 5
PURGE_WINDOW = 20
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
# FEATURE NEUTRALIZATION vs MARKET
# ============================================================

class FeatureNeutralizer(BaseEstimator, TransformerMixin):

    def __init__(self, market_ret):
        self.market_ret = market_ret.values.reshape(-1, 1)
        self.models_: Dict[str, LinearRegression] = {}

    def fit(self, X, y=None):
        self.models_ = {}
        for col in X.columns:
            lr = LinearRegression()
            lr.fit(self.market_ret, X[col].values)
            self.models_[col] = lr
        return self

    def transform(self, X):
        Xn = X.copy()
        for col in X.columns:
            pred = self.models_[col].predict(self.market_ret)
            Xn[col] = X[col] - pred
        return Xn


# ============================================================
# LOADING & FEATURE SELECTION
# ============================================================

def load_and_prepare(path):
    df = pd.read_csv(path)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    return df.sort_values([SYMBOL_COL, DATE_COL]).reset_index(drop=True)


def build_alpha(df):

    # Future market return zaten master_df'te olmalı
    df[ALPHA_COL] = df[FUT_RET_COL] - df[MARKET_FUT_RET_COL]

    # Alpha'nın binarize edilmiş versiyonu:
    # 1 → endeksi yendi
    df["y_alpha"] = (df[ALPHA_COL] > 0).astype(int)

    return df.dropna(subset=["y_alpha"]).reset_index(drop=True)


def select_features(df):

    drop_cols = {
        SYMBOL_COL, DATE_COL,
        FUT_RET_COL, MARKET_FUT_RET_COL,
        ALPHA_COL, "y_alpha",
        "price_open","price_high","price_low","price_adj_close"
    }

    drop_cols |= {c for c in df.columns if "future_" in c or c.startswith("y_")}

    features = [
        c for c in df.columns
        if c not in drop_cols and pd.api.types.is_numeric_dtype(df[c])
    ]

    X = df[features].copy()
    X = X.replace([np.inf, -np.inf], np.nan).fillna(X.median())

    return X, df["y_alpha"]


# ============================================================
# METRICS & ROC PLOT
# ============================================================

def save_metrics_and_plots(y_true, y_prob, fold_auc_list):

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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

    metrics_df.to_csv(f"{RESULTS_DIR}/metrics_{timestamp}.csv", index=False)

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    plt.plot([0, 1], [0, 1], "k--")
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.title("ROC Curve — ALPHA Model")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/roc_curve_{timestamp}.png")
    plt.close()


# ============================================================
# TRAIN PIPELINE — ALPHA MODEL
# ============================================================

def run_pipeline():

    print(">> Loading data...")
    df = load_and_prepare(DATA_PATH)

    print(">> Building ALPHA target...")
    df = build_alpha(df)

    print(">> Selecting features...")
    X, y = select_features(df)

    print(">> Neutralizing features...")
    neutralizer = FeatureNeutralizer(df[MARKET_RET_COL].fillna(0))
    Xn = neutralizer.fit_transform(X)

    X_mat = Xn.values
    y_vec = y.values

    print(">> Purged CV Training... (ALPHA)")
    cv = PurgedTimeSeriesSplit(N_SPLITS, PURGE_WINDOW, EMBARGO_PCT)

    oof_pred = np.zeros(len(df))
    fold_aucs = []

    for fold, (tr, te) in enumerate(cv.split(X_mat), 1):

        model = CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            depth=6,
            learning_rate=0.05,
            iterations=500,
            verbose=False
        )

        model.fit(Pool(X_mat[tr], y_vec[tr]), eval_set=Pool(X_mat[te], y_vec[te]))

        prob = model.predict_proba(X_mat[te])[:, 1]
        oof_pred[te] = prob

        auc = roc_auc_score(y_vec[te], prob)
        fold_aucs.append(auc)
        print(f"Fold {fold} AUC (alpha): {auc:.3f}")

    print("\n>> Overall OOF performance:")
    save_metrics_and_plots(y_vec, oof_pred, fold_aucs)

    print("\n>> Training FINAL ALPHA model on ALL data...")
    final_model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=6,
        learning_rate=0.05,
        iterations=700,
        verbose=False
    )
    final_model.fit(Pool(X_mat, y_vec))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path = f"{RESULTS_DIR}/catboost_alpha_{ts}.cbm"
    final_model.save_model(model_path)

    neutralizer_path = f"{RESULTS_DIR}/neutralizer_alpha_{ts}.pkl"
    joblib.dump({"neutralizer": neutralizer, "features": list(X.columns)}, neutralizer_path)

    print(f"\n>> Saved ALPHA model: {model_path}")
    print(f">> Saved neutralizer: {neutralizer_path}")

    print("\n✨ ALPHA PIPELINE COMPLETED.\n")


if __name__ == "__main__":
    run_pipeline()
