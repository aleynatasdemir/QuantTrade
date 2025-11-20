"""
QUANT-TRADE FULL PIPELINE — ALPHA 120D (LEAKAGE-FREE FINAL)
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
RESULTS_DIR = "model_results_alpha_120d"
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOL_COL = "symbol"
DATE_COL = "date"

HORIZON = 120
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"
ALPHA_COL = f"alpha_{HORIZON}d"

MARKET_RET_COL = "macro_bist100_roc_5d"   # neutralizer içinde kullanılıyor

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
# FEATURE NEUTRALIZER — CLEAN (Leakage-free inside CV)
# ============================================================

class FeatureNeutralizer(BaseEstimator, TransformerMixin):

    def __init__(self, market_ret):
        # NaN → 0
        mr = pd.Series(market_ret).fillna(0).values.reshape(-1, 1)
        self.market_ret = mr
        self.models_: Dict[str, LinearRegression] = {}

    def fit(self, X, y=None):
        mr = self.market_ret  # zaten NaN'tan arındırıldı
        self.models_ = {}
        for col in X.columns:
            lr = LinearRegression()
            lr.fit(mr, X[col].values)
            self.models_[col] = lr
        return self

    def transform(self, X, market_ret=None):
        if market_ret is None:
            mr = self.market_ret
        else:
            mr = pd.Series(market_ret).fillna(0).values.reshape(-1, 1)  # <-- kritik

        Xn = X.copy()
        for col in X.columns:
            pred = self.models_[col].predict(mr)
            Xn[col] = X[col] - pred
        return Xn




# ============================================================
# LOAD + PREP
# ============================================================

def load_and_prepare(path):
    df = pd.read_csv(path)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    return df.sort_values([SYMBOL_COL, DATE_COL]).reset_index(drop=True)



# ============================================================
# ALPHA TARGET
# ============================================================

def build_alpha(df):
    df[ALPHA_COL] = df[FUT_RET_COL] - df[MARKET_FUT_RET_COL]
    df["y_alpha"] = (df[ALPHA_COL] > 0).astype(int)
    return df.dropna(subset=["y_alpha"]).reset_index(drop=True)



# ============================================================
# FEATURE SELECTION — CLEAN
# ============================================================

def select_features(df):

    # DROP everything containing future_ OR y_
    drop_cols = {c for c in df.columns if "future_" in c or c.startswith("y_")}

    # DROP all alpha_* except the target we're training (alpha_120d)
    drop_cols |= {c for c in df.columns if c.startswith("alpha_") and c != ALPHA_COL}

    # DROP id columns + target + market future
    drop_cols |= {
        SYMBOL_COL, DATE_COL,
        ALPHA_COL,       # target
        FUT_RET_COL,     # future return
        MARKET_FUT_RET_COL
    }

    # DROP raw price data
    drop_cols |= {"price_open", "price_high", "price_low", "price_adj_close"}

    # Final feature list
    features = [
        c for c in df.columns
        if c not in drop_cols and pd.api.types.is_numeric_dtype(df[c])
    ]

    X = df[features].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    return X, df["y_alpha"], features



# ============================================================
# METRICS + ROC PLOT
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
        "Fold AUCs": [fold_auc_list]
    })
    metrics_df.to_csv(f"{RESULTS_DIR}/metrics_{ts}.csv", index=False)

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    plt.plot([0, 1], [0, 1], "k--")
    plt.title("ROC Curve — ALPHA 120d Model")
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/roc_curve_{ts}.png")
    plt.close()



# ============================================================
# TRAIN PIPELINE — CLEAN, LEAKAGE-FREE
# ============================================================

def run_pipeline():

    print(">> Loading data...")
    df = load_and_prepare(DATA_PATH)

    print(">> Building ALPHA target...")
    df = build_alpha(df)

    print(">> Selecting features...")
    X, y, feature_names = select_features(df)

    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)

    X_mat = X.values
    y_vec = y.values

    print(">> Starting Purged CV Training (Leakage-Free)...")

    cv = PurgedTimeSeriesSplit(N_SPLITS, PURGE_WINDOW, EMBARGO_PCT)

    oof_pred = np.zeros(len(df))
    fold_aucs = []

    for fold, (tr, te) in enumerate(cv.split(X_mat), 1):

        # ------------------------- 
        # Leakage-free neutralizer
        # -------------------------
        nz = FeatureNeutralizer(
            df[MARKET_RET_COL].iloc[tr].fillna(0)
        )
        nz.fit(X.iloc[tr])

        Xtr_n = nz.transform(X.iloc[tr])
        Xte_n = nz.transform(X.iloc[te], market_ret=df[MARKET_RET_COL].iloc[te])

        # -------------------------
        # Model Fit
        # -------------------------
        model = CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            depth=6,
            learning_rate=0.05,
            iterations=500,
            verbose=False
        )

        model.fit(Pool(Xtr_n, y_vec[tr]), eval_set=Pool(Xte_n, y_vec[te]))

        prob = model.predict_proba(Xte_n)[:, 1]
        oof_pred[te] = prob

        auc = roc_auc_score(y_vec[te], prob)
        fold_aucs.append(auc)
        print(f"Fold {fold} AUC: {auc:.3f}")

    print("\n>> OOF Results:")
    save_metrics_and_plots(y_vec, oof_pred, fold_aucs)

    # ======================================================
    # FINAL MODEL TRAINING (Full data, leakage-free neutralizer)
    # ======================================================

    print("\n>> Training Final Model on ALL data...")

    final_nz = FeatureNeutralizer(df[MARKET_RET_COL].fillna(0))
    final_nz.fit(X)
    X_all_n = final_nz.transform(X)

    final_model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=6,
        learning_rate=0.05,
        iterations=700,
        verbose=False
    )
    final_model.fit(Pool(X_all_n, y_vec))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path = f"{RESULTS_DIR}/catboost_alpha120d_{ts}.cbm"
    final_model.save_model(model_path)

    neutralizer_path = f"{RESULTS_DIR}/neutralizer_alpha120d_{ts}.pkl"
    joblib.dump({"neutralizer": final_nz, "features": feature_names}, neutralizer_path)

    print("\n>> Saved MODEL:", model_path)
    print(">> Saved NEUTRALIZER:", neutralizer_path)

    print("\n✨ TRAINING COMPLETED — CLEAN, LEAKAGE-FREE ✔️\n")



if __name__ == "__main__":
    run_pipeline()
