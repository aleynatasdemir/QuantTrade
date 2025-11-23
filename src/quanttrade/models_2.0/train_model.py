"""
QUANT-TRADE FULL PIPELINE — ALPHA 20D (LEAKAGE-FREE FINAL)
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
        """
        Args:
            factors: Eğitim setine ait faktör kolonları (DataFrame)
            sector: Eğitim setine ait sektör etiketleri (Series, opsiyonel)
        """
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
        """
        Faktörler + sektör dummy'lerinden tasarım matrisi (F) üretir.
        """
        # Faktör kolonlarını aynı sıraya sok
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
            # Eğitimde kullanılan dummy kolonlarını koru
            dummies = dummies.reindex(columns=self.sector_dummy_cols_, fill_value=0.0)
            F_parts.append(dummies.values.astype(float))

        # Hepsini birleştir
        F = np.hstack(F_parts)
        return F

    def fit(self, X: pd.DataFrame, y=None):
        """
        Eğitim seti features X için faktör/sektöre göre regresyon katsayılarını öğren.
        """
        # Sektör dummy kolonlarını belirle
        if self.sector is not None:
            dummies = pd.get_dummies(self.sector.astype(str), prefix="sector")
            self.sector_dummy_cols_ = list(dummies.columns)
        else:
            self.sector_dummy_cols_ = None

        # Tasarım matrisi (train)
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
        """
        Verilen X için faktör/sektör etkisini çıkar.

        Args:
            X: Nötralize edilecek feature matrisi (test veya train)
            factors: Aynı satırlara ait faktör DataFrame'i
            sector: Aynı satırlara ait sektör etiketleri

        Returns:
            Xn: Nötralize edilmiş feature matrisi
        """
        # Eğer parametre verilmezse eğitimdeki ile aynı seti kullan
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

    # === QUINTILE-BASED TARGET ===
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

    Böylece model sektörler arası seviye farkını değil,
    sektör içi outlier'ları öğrenir.
    """

    def __init__(self):
        # sector -> {"mean": Series, "std": Series}
        self.stats_ = {}

    def fit(self, X: pd.DataFrame, sector: pd.Series):
        sector = sector.astype(str)
        self.stats_ = {}

        for sec in sector.unique():
            mask = (sector == sec)
            X_sec = X.loc[mask]

            mean = X_sec.mean()
            std = X_sec.std(ddof=0).replace(0, 1.0)  # 0 olan std'leri 1 yap

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

    # y_triple_20d dışındaki tüm future_* ve y_* kolonlarını at
    drop_cols = {
        c for c in df.columns
        if "future_" in c or (c.startswith("y_") and c != "y_triple_20d")
    }

    drop_cols |= {
        SYMBOL_COL,
        DATE_COL,
        "y_triple_20d",   # target olduğu için atılacak
        ALPHA_COL,
        FUT_RET_COL,
        MARKET_FUT_RET_COL,
        SECTOR_COL
    }

    drop_cols |= {
        "price_open","price_high","price_low","price_adj_close"
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
        "Fold AUCs": [fold_auc_list]
    })
    metrics_df.to_csv(f"{RESULTS_DIR}/metrics_{ts}.csv", index=False)

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    plt.plot([0, 1], [0, 1], "k--")
    plt.title("ROC Curve — ALPHA 20d Model")
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{RESULTS_DIR}/roc_curve_{ts}.png")
    plt.close()


# ============================================================
# TRAIN PIPELINE (train+valid only)
# ============================================================

def run_pipeline():

    print(">> Loading data...")
    df = load_and_prepare(DATA_PATH)


    # triple-barrier yönelim etiketi
    df = df.dropna(subset=["y_triple_20d"]).reset_index(drop=True)
    df["y_triple_20d"] = df["y_triple_20d"].astype(int)


    # --------- BURASI KRİTİK: sadece train + valid kullan ----------
    print(">> Filtering to TRAIN + VALID only...")
    df_tv = df[df["dataset_split"].isin(["train", "valid"])].reset_index(drop=True)

    print(">> Selecting features...")
    X, feature_names = select_features(df_tv)
    y = df_tv["y_triple_20d"].reset_index(drop=True)


    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)

    X_mat = X.values
    y_vec = y.values


    factors_all = pd.DataFrame(index=df_tv.index).reset_index(drop=True)

    if SECTOR_COL not in df_tv.columns:
        raise ValueError(f"Sektör kolonu bulunamadı: {SECTOR_COL}")

    sector_all = df_tv[SECTOR_COL].fillna("other").astype(str).reset_index(drop=True)

    print(">> Starting Purged CV Training (Leakage-Free)...")

    cv = PurgedTimeSeriesSplit(N_SPLITS, PURGE_WINDOW, EMBARGO_PCT)

    oof_pred = np.zeros(len(df_tv))
    fold_aucs = []

    for fold, (tr, te) in enumerate(cv.split(X_mat), 1):

        # 0) Fold'un X, faktör ve sektör setlerini ayır
        X_tr = X.iloc[tr].reset_index(drop=True)
        X_te = X.iloc[te].reset_index(drop=True)

        factors_tr = factors_all.iloc[tr].reset_index(drop=True)
        factors_te = factors_all.iloc[te].reset_index(drop=True)

        sector_tr = sector_all.iloc[tr].reset_index(drop=True)
        sector_te = sector_all.iloc[te].reset_index(drop=True)

        # 1) SEKTÖR Z-SCORE NORMALİZASYONU
        #    - Her sektörde feature'ları kendi mean/std'sine göre normalize ediyoruz.
        #    - Neden? Sektör içi outlier yakalamak için.
        sec_scaler = SectorStandardScaler()
        sec_scaler.fit(X_tr, sector_tr)

        Xtr_s = sec_scaler.transform(X_tr, sector_tr)
        Xte_s = sec_scaler.transform(X_te, sector_te)

        # 2) ÇOK FAKTÖRLÜ + SEKTÖR NÖTRALİZASYON
        #    - Market + FX + faiz + sektör dummy etkilerini çıkarıyoruz.
        nz = FeatureNeutralizer(factors_tr, sector_tr)
        nz.fit(Xtr_s)

        Xtr_n = nz.transform(Xtr_s, factors_tr, sector_tr)
        Xte_n = nz.transform(Xte_s, factors_te, sector_te)

        # 3) MODEL EĞİTİMİ — her fold için nötralize + normalize edilmiş feature'larla
        model = CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            depth=6,
            learning_rate=0.05,
            iterations=700,
            verbose=False,
        )
        model.fit(Xtr_n, y.iloc[tr])

        prob = model.predict_proba(Xte_n)[:, 1]
        oof_pred[te] = prob

        auc = roc_auc_score(y_vec[te], prob)
        fold_aucs.append(auc)

        print(f"Fold {fold} AUC: {auc:.3f}")


    print("\n>> OOF Results (train+valid only):")
    save_metrics_and_plots(y_vec, oof_pred, fold_aucs)

    # ======================================================
    # FINAL MODEL (train+valid üzerinde)
    # ======================================================

    print("\n>> Training Final Model on TRAIN+VALID data...")

    # Tüm train+valid için faktör ve sektör
    final_factors = factors_all  # zaten reset_index yaptık
    final_sector = sector_all

    # 1) SEKTÖR Z-SCORE (train+valid tamamı)
    sec_scaler_final = SectorStandardScaler()
    sec_scaler_final.fit(X, final_sector)
    X_s = sec_scaler_final.transform(X, final_sector)

    # 2) ÇOK FAKTÖRLÜ + SEKTÖR NÖTRALİZASYON
    final_nz = FeatureNeutralizer(final_factors, final_sector)
    final_nz.fit(X_s)
    X_all_n = final_nz.transform(X_s, final_factors, final_sector)

    # 3) MODEL EĞİTİMİ
    final_model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=6,
        learning_rate=0.05,
        iterations=700,
        verbose=False
    )
    final_model.fit(Pool(X_all_n, y_vec))

    # ======================================================
    # FEATURE IMPORTANCE (FINAL MODEL)
    # ======================================================
    print("\n>> Calculating feature importance (CatBoost)...")

    # CatBoost'tan önem skorlarını çek
    importances = final_model.get_feature_importance(Pool(X_all_n, y_vec))

    fi_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    # En önemli ilk 30 feature'ı yazdır
    print("\nTop 30 features by importance:")
    print(fi_df.head(30).to_string(index=False))

    # Özellikle rejim feature'larına bakalım
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

    # Timestamp oluştur
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # İstersen CSV olarak da kaydedelim
    fi_path = f"{RESULTS_DIR}/feature_importance_{ts}.csv"
    fi_df.to_csv(fi_path, index=False)
    print("\nFeature importance CSV kaydedildi:", fi_path)

    model_path = f"{RESULTS_DIR}/catboost_alpha20d_{ts}.cbm"
    final_model.save_model(model_path)
    np.save(f"{RESULTS_DIR}/oof_pred_m1_{ts}.npy", oof_pred)

    neutralizer_path = f"{RESULTS_DIR}/neutralizer_alpha20d_{ts}.pkl"
    joblib.dump(
    {
        "sector_scaler": sec_scaler_final,
        "neutralizer": final_nz,
        "features": feature_names,
        "factors": final_factors, 
        "sector": final_sector,
    },
    neutralizer_path
)



    print("\n>> Saved MODEL:", model_path)
    print(">> Saved NEUTRALIZER:", neutralizer_path)
    print("\n✨ TRAINING COMPLETED — CLEAN, LEAKAGE-FREE ✔️\n")



if __name__ == "__main__":
    run_pipeline()
