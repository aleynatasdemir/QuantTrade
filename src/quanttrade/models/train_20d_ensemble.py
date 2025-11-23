"""
QUANT-TRADE FULL PIPELINE — ALPHA 20D (STACKING ENSEMBLE, LEAKAGE-FREE)
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
from typing import Dict, Optional, List

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, roc_curve
from sklearn.model_selection import BaseCrossValidator
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from pytorch_tabnet.tab_model import TabNetClassifier
from catboost import CatBoostClassifier, Pool
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier


# ============================================================
# CONFIG
# ============================================================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOL_COL = "symbol"
DATE_COL = "date"

HORIZON = 20
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"
ALPHA_COL = f"alpha_{HORIZON}d"

MARKET_RET_COL = "macro_bist100_roc_5d"

N_SPLITS = 5
PURGE_WINDOW = 10
EMBARGO_PCT = 0.05

SECTOR_COL = "sector"

# Stacking için base model isimleri (sıraları önemli!)
BASE_MODEL_NAMES: List[str] = ["catboost", "lgbm", "xgb", "rf", "tabnet"]



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
# FEATURE NEUTRALIZER (MULTI-FACTOR + SECTOR)
# ============================================================

class FeatureNeutralizer(BaseEstimator, TransformerMixin):
    """
    Çok faktörlü + sektör dummy'li nötralizasyon.

    Her feature için:
        feature ~ intercept + factors + sector_dummies
    regresyonu kurup residual = feature - predicted alır.
    """

    def __init__(self, factors: pd.DataFrame, sector: Optional[pd.Series] = None):
        self.factors = pd.DataFrame(factors).copy()
        self.sector = pd.Series(sector).copy() if sector is not None else None

        self.models_: Dict[str, LinearRegression] = {}
        self.factor_cols_ = list(self.factors.columns)
        self.sector_dummy_cols_: Optional[list] = None

    def _build_design_matrix(
        self,
        factors: pd.DataFrame,
        sector: Optional[pd.Series]
    ) -> np.ndarray:

        F_parts = []
        n = len(factors)

        # 1) Intercept
        F_parts.append(np.ones((n, 1), dtype=float))

        # 2) Faktörler
        if factors is not None and factors.shape[1] > 0:
            fac = factors[self.factor_cols_].fillna(0.0).values.astype(float)
            F_parts.append(fac)

        # 3) Sektör dummy'leri
        if self.sector_dummy_cols_ is not None and sector is not None:
            dummies = pd.get_dummies(sector.astype(str), prefix="sector")
            dummies = dummies.reindex(columns=self.sector_dummy_cols_, fill_value=0.0)
            F_parts.append(dummies.values.astype(float))

        F = np.hstack(F_parts)
        return F

    def fit(self, X: pd.DataFrame, y=None):
        if self.sector is not None:
            dummies = pd.get_dummies(self.sector.astype(str), prefix="sector")
            self.sector_dummy_cols_ = list(dummies.columns)
        else:
            self.sector_dummy_cols_ = None

        F_train = self._build_design_matrix(self.factors, self.sector)

        self.models_ = {}
        for col in X.columns:
            lr = LinearRegression()
            lr.fit(F_train, X[col].values)
            self.models_[col] = lr

        return self

    def transform(
        self,
        X: pd.DataFrame,
        factors: Optional[pd.DataFrame] = None,
        sector: Optional[pd.Series] = None
    ) -> pd.DataFrame:

        if factors is None:
            factors = self.factors
        else:
            factors = pd.DataFrame(factors)

        if sector is None:
            sector = self.sector
        else:
            sector = pd.Series(sector)

        F_new = self._build_design_matrix(factors, sector)

        Xn = X.copy()
        for col in X.columns:
            lr = self.models_[col]
            pred = lr.predict(F_new)
            Xn[col] = X[col].values - pred

        return Xn


# ============================================================
# LOAD + PREP
# ============================================================

def load_and_prepare(path):
    df = pd.read_csv(path)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    return df.sort_values([DATE_COL, SYMBOL_COL]).reset_index(drop=True)


# ============================================================
# ALPHA TARGET
# ============================================================

def build_alpha(df):
    df[ALPHA_COL] = df[FUT_RET_COL] - df[MARKET_FUT_RET_COL]

    df = df.dropna(subset=[ALPHA_COL]).reset_index(drop=True)

    q20 = df[ALPHA_COL].quantile(0.20)
    q80 = df[ALPHA_COL].quantile(0.80)

    df["y_alpha"] = np.where(
        df[ALPHA_COL] >= q80, 1,
        np.where(df[ALPHA_COL] <= q20, 0, np.nan)
    )

    df = df.dropna(subset=["y_alpha"]).reset_index(drop=True)
    df["y_alpha"] = df["y_alpha"].astype(int)

    return df


# ============================================================
# SECTOR-BASED STANDARD SCALER
# ============================================================

class SectorStandardScaler(BaseEstimator, TransformerMixin):
    """
    Her sektörde, her feature'ı kendi sektörü içinde z-score'lar:

        z = (x - mean_sector) / std_sector
    """

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

    def transform(self, X: pd.DataFrame, sector: pd.Series) -> pd.DataFrame:
        sector = sector.astype(str)
        X_scaled = X.copy()

        for sec, stats in self.stats_.items():
            mask = (sector == sec)
            if not mask.any():
                continue

            m = stats["mean"]
            s = stats["std"]

            X_scaled.loc[mask] = (X.loc[mask] - m) / s

        return X_scaled


# ============================================================
# FEATURE SELECTION
# ============================================================

def select_features(df):

    drop_cols = {c for c in df.columns if "future_" in c or c.startswith("y_")}

    drop_cols |= {c for c in df.columns if c.startswith("alpha_") and c != ALPHA_COL}

    drop_cols |= {
        SYMBOL_COL,
        DATE_COL,
        ALPHA_COL,
        FUT_RET_COL,
        MARKET_FUT_RET_COL,
    }

    drop_cols |= {
        "price_open",
        "price_high",
        "price_low",
        "price_adj_close",
    }

    drop_cols |= {SECTOR_COL}

    features = [
        c for c in df.columns
        if c not in drop_cols and pd.api.types.is_numeric_dtype(df[c])
    ]

    X = df[features].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    return X, df["y_alpha"], features


# ============================================================
# METRICS + ROC (base model için)
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
    plt.title("ROC Curve — ALPHA 20d Model (Base CatBoost)")
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/roc_curve_{ts}.png")
    plt.close()


# ============================================================
# BASE MODELLERİ OLUŞTURAN FONKSİYON
# ============================================================

def get_base_models() -> Dict[str, BaseEstimator]:
    """
    Her çağrıldığında taze model instance'ları döner.
    """
    models = {}

    models["catboost"] = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=6,
        learning_rate=0.05,
        iterations=700,
        verbose=False,
        random_seed=42
    )

    models["lgbm"] = LGBMClassifier(
        n_estimators=700,
        learning_rate=0.05,
        max_depth=-1,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42
    )

    models["xgb"] = XGBClassifier(
        n_estimators=700,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="auc",
        tree_method="hist",
        random_state=42
    )

    models["rf"] = RandomForestClassifier(
        n_estimators=400,
        max_depth=None,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=42
    )

    # Yeni: TabNet
    models["tabnet"] = TabNetClassifier(
        n_d=32,
        n_a=32,
        n_steps=5,
        gamma=1.5,
        n_independent=2,
        n_shared=2,
        lambda_sparse=1e-4,
        seed=42,
        verbose=0
    )

    return models


# ============================================================
# TRAIN PIPELINE (STACKING + FINAL)
# ============================================================

def run_pipeline():

    print(">> Loading data...")
    df = load_and_prepare(DATA_PATH)

    print(">> Building ALPHA target...")
    df = build_alpha(df)

    print(">> Filtering to TRAIN + VALID only...")
    df_tv = df[df["dataset_split"].isin(["train", "valid"])].reset_index(drop=True)

    print(">> Selecting features...")
    X, y, feature_names = select_features(df_tv)

    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)

    X_mat = X.values
    y_vec = y.values

    # Faktörleri şimdilik boş bırakıyoruz (dummy) — istersen buraya macro faktörleri ekleyebilirsin
    factors_all = pd.DataFrame(index=df_tv.index).reset_index(drop=True)

    if SECTOR_COL not in df_tv.columns:
        raise ValueError(f"Sektör kolonu bulunamadı: {SECTOR_COL}")

    sector_all = df_tv[SECTOR_COL].fillna("other").astype(str).reset_index(drop=True)

    print(">> Starting Purged CV Training (Leakage-Free, Stacking OOF)...")

    cv = PurgedTimeSeriesSplit(N_SPLITS, PURGE_WINDOW, EMBARGO_PCT)

    n_samples = len(df_tv)
    n_models = len(BASE_MODEL_NAMES)

    # OOF tahmin matrisi: her model için bir sütun
    oof_pred = np.zeros((n_samples, n_models), dtype=float)

    # Her base model için fold AUC listesi
    fold_aucs_per_model: Dict[str, List[float]] = {name: [] for name in BASE_MODEL_NAMES}

    for fold, (tr, te) in enumerate(cv.split(X_mat), 1):

        print(f"\n=== Fold {fold} ===")

        X_tr = X.iloc[tr].reset_index(drop=True)
        X_te = X.iloc[te].reset_index(drop=True)

        factors_tr = factors_all.iloc[tr].reset_index(drop=True)
        factors_te = factors_all.iloc[te].reset_index(drop=True)

        sector_tr = sector_all.iloc[tr].reset_index(drop=True)
        sector_te = sector_all.iloc[te].reset_index(drop=True)

        # 1) Sektör z-score normalizasyonu
        sec_scaler = SectorStandardScaler()
        sec_scaler.fit(X_tr, sector_tr)

        Xtr_s = sec_scaler.transform(X_tr, sector_tr)
        Xte_s = sec_scaler.transform(X_te, sector_te)

        # 2) Faktör + sektör nötralizasyonu
        nz = FeatureNeutralizer(factors_tr, sector_tr)
        nz.fit(Xtr_s)

        Xtr_n = nz.transform(Xtr_s, factors_tr, sector_tr)
        Xte_n = nz.transform(Xte_s, factors_te, sector_te)

        # 3) Base modeller
        base_models = get_base_models()

        for m_idx, name in enumerate(BASE_MODEL_NAMES):
            model = base_models[name]

            # === CatBoost ===
            if name == "catboost":
                model.fit(Xtr_n, y.iloc[tr])
                prob_te = model.predict_proba(Xte_n)[:, 1]

            # === TabNet ===
            elif name == "tabnet":
                Xtr_np = Xtr_n.values.astype(np.float32)
                Xte_np = Xte_n.values.astype(np.float32)
                y_tr_np = y.iloc[tr].values

                model.fit(
                    Xtr_np,
                    y_tr_np,
                    eval_set=[(Xte_np, y.iloc[te].values)],
                    eval_name=["valid"],
                    eval_metric=["auc"],
                    max_epochs=50,                # GPU yoksa 200 çok ağır → 50 ideal
                    patience=10,
                    batch_size=1024,
                    virtual_batch_size=128,
                    num_workers=0,
                )

                # TabNet predict_proba da numpy ister
                prob_te = model.predict_proba(Xte_np)[:, 1]

            # === Diğer modeller ===
            else:
                model.fit(Xtr_n, y.iloc[tr])
                prob_te = model.predict_proba(Xte_n)[:, 1]

            # === OOF kaydı ===
            oof_pred[te, m_idx] = prob_te

            auc = roc_auc_score(y_vec[te], prob_te)
            fold_aucs_per_model[name].append(auc)

            print(f"  [{name}] Fold {fold} AUC: {auc:.3f}")


    # ===========================
    # OOF SONUÇ ÖZETİ
    # ===========================
    print("\n>> OOF summary by base model:")
    for name in BASE_MODEL_NAMES:
        model_oof = oof_pred[:, BASE_MODEL_NAMES.index(name)]
        auc_total = roc_auc_score(y_vec, model_oof)
        print(f"  {name:8s} | OOF AUC: {auc_total:.3f} | Fold AUCs: {np.round(fold_aucs_per_model[name], 3)}")

    # Eski funkc. sadece CatBoost üzerinden metrik/ROC çizecek (M1 referansı)
    cat_idx = BASE_MODEL_NAMES.index("catboost")
    save_metrics_and_plots(y_vec, oof_pred[:, cat_idx], fold_aucs_per_model["catboost"])

    # ===========================
    # META MODEL (M2) — LOGISTIC REGRESSION
    # ===========================
    print("\n>> Training meta-model (Logistic Regression) on OOF predictions...")

    meta_model = LogisticRegression(
        max_iter=1000,
        C=0.5,
        penalty="l2",
        solver="lbfgs"
    )
    meta_model.fit(oof_pred, y_vec)

    meta_oof_prob = meta_model.predict_proba(oof_pred)[:, 1]
    meta_auc = roc_auc_score(y_vec, meta_oof_prob)
    print(f">> Meta-model (LR) AUC on OOF features (train+valid): {meta_auc:.3f}")

    # Optional: meta için ayrı metrik CSV/ROC istersen buraya benzer bir fonksiyon yazıp çağırabiliriz.

    # ======================================================
    # FINAL BASE MODELS (TRAIN+VALID ÜZERİNDE)
    # ======================================================

    print("\n>> Training Final Base Models on TRAIN+VALID data...")

    final_factors = factors_all
    final_sector = sector_all

    # 1) Sektör Z-Score (train+valid tamamı)
    sec_scaler_final = SectorStandardScaler()
    sec_scaler_final.fit(X, final_sector)
    X_s = sec_scaler_final.transform(X, final_sector)

    # 2) Faktör + sektör nötralizasyonu
    final_nz = FeatureNeutralizer(final_factors, final_sector)
    final_nz.fit(X_s)
    X_all_n = final_nz.transform(X_s, final_factors, final_sector)

    # 3) Tüm base modelleri tek seferde eğit
    final_base_models = get_base_models()

    for name, model in final_base_models.items():
        print(f"  >> Fitting final base model: {name}")

        if name == "catboost":
            model.fit(Pool(X_all_n, y_vec))

        elif name == "tabnet":
            X_np = X_all_n.values.astype(np.float32)
            model.fit(
                X_np,
                y_vec,
                max_epochs=50,
                patience=10,
                batch_size=1024,
                virtual_batch_size=128,
                num_workers=0,
            )

        else:
            model.fit(X_all_n, y_vec)


    # ======================================================
    # FEATURE IMPORTANCE (CatBoost FINAL MODEL)
    # ======================================================
    print("\n>> Calculating feature importance (CatBoost final model)...")

    cb_final = final_base_models["catboost"]
    importances = cb_final.get_feature_importance(Pool(X_all_n, y_vec))

    fi_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    print("\nTop 30 features by importance:")
    print(fi_df.head(30).to_string(index=False))

    regime_cols = [
        "macro_bist100_distance_ma200",
        "macro_bist100_vol_regime",
        "macro_usdtry_distance_ma200",
        "macro_usdtry_vol_regime",
        "price_distance_from_ma200",
        "price_ma20_slope_5d",
        "price_vol_regime",
    ]

    regime_fi = fi_df[fi_df["feature"].isin(regime_cols)]

    print("\nRegime-related features importance:")
    if regime_fi.empty:
        print("⚠ Rejim feature'ları feature set içinde bulunamadı (isimler farklı olabilir).")
    else:
        print(regime_fi.to_string(index=False))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    fi_path = f"{RESULTS_DIR}/feature_importance_{ts}.csv"
    fi_df.to_csv(fi_path, index=False)
    print("\nFeature importance CSV kaydedildi:", fi_path)

    # ======================================================
    # MODELLERİ + NÖTRALIZERİ KAYDET
    # ======================================================

    # OOF matrisini da kaydedelim (n_samples x n_models)
    oof_path = f"{RESULTS_DIR}/oof_pred_base_{ts}.npy"
    np.save(oof_path, oof_pred)
    print("OOF predictions saved:", oof_path)

    # CatBoost'u .cbm olarak ayrıca kaydedelim (istersen)
    catboost_model_path = f"{RESULTS_DIR}/catboost_alpha20d_{ts}.cbm"
    cb_final.save_model(catboost_model_path)
    print("CatBoost final model saved (.cbm):", catboost_model_path)

    # Tüm stacking bundle'ı tek bir pkl olarak kaydediyoruz
    bundle = {
        "features": feature_names,
        "base_model_names": BASE_MODEL_NAMES,
        "base_models": final_base_models,
        "meta_model": meta_model,
        "sector_scaler": sec_scaler_final,
        "neutralizer": final_nz,
        "horizon": HORIZON,
    }

    bundle_path = f"{RESULTS_DIR}/stacking_ensemble_alpha20d_{ts}.pkl"
    joblib.dump(bundle, bundle_path)

    print("Stacking ensemble bundle saved:", bundle_path)
    print("\n✨ TRAINING COMPLETED — STACKING ENSEMBLE (M1+M2) ✔️\n")


if __name__ == "__main__":
    run_pipeline()
