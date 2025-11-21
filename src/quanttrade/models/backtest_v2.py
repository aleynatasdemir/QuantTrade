"""
QUANT-TRADE ALPHA BACKTESTER 2.0 (REALISTIC, NON-OVERLAP)

- Son ALPHA CatBoost + Neutralizer'ı yükler  (model_results_alpha_10d/)
- Sadece TEST döneminde skor üretir (dataset_split == 'test')
- Her 10 günde 1 kere (HORIZON) TOP_K hisse alır, 10 günlük getirisiyle backtest yapar
- Kullanılan realized getiri: future_return_10d (nominal)
- Benchmark: market_future_return_10d   (index)
- Strateji getirisi: future_return_10d (TOP_K ortalama) - trading_cost
- Alpha: strategy_ret - benchmark_ret
- Overlap YOK (her trade 10 gün sürer)
- Ekstra:
    * Likidite filtresi (min turnover)
    * Opsiyonel watchlist filtresi
    * Transaction cost + slippage (round-trip)
- Sonuçlar: backtest_results_alpha_20d/ klasörüne yazılır
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

FACTOR_COLS = [
    "macro_bist100_roc_20d",      # Genel market faktörü
    "macro_usdtry_vs_bist100",    # Kur faktörü
    "macro_tcmb_rate_change_5d",  # Faiz şok faktörü
]

SECTOR_COL = "sector"

TOP_K = 5                     # her rebalance gününde alınan hisse sayısı
MIN_STOCKS_PER_DAY = TOP_K     # universe'te en az bu kadar hisse olsun

# --- Likidite filtresi ---
PRICE_COL = "price_close"
VOLUME_COL = "price_volume"
MIN_TURNOVER_TL = 5_000_000    # minimum günlük TL hacim (price * volume)

# --- Transaction cost + slippage ---
# Örn: 0.05% komisyon + 0.05% slippage = 0.10% round-trip
COMMISSION_BPS = 5             # 0.05%
SLIPPAGE_BPS = 5               # 0.05%
ROUNDTRIP_COST = (COMMISSION_BPS + SLIPPAGE_BPS) / 10_000  # oransal

# --- Opsiyonel: universe filtresi (sadece bu hisseler) ---
WATCHLIST: Optional[List[str]] = None
# Örnek:
# WATCHLIST = ["KCHOL","SAHOL","DOHOL","THYAO","ARCLK","ASELS","EREGL","FROTO","SISE","TUPRS"]


# ==========================
# FEATURE NEUTRALIZER CLASS
#   (Eğitim tarafındakiyle aynı isim/signature olmalı)
# ==========================

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


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Dosya bulunamadı: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# MAIN
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Son ALPHA modelini ve neutralizer'ı buluyorum...")
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha20d_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha20d_*.pkl"))

    print(f"   Model      : {model_path}")
    print(f"   Neutralizer: {neutralizer_path}")

    # Model
    model = CatBoostClassifier()
    model.load_model(model_path)

    # Neutralizer + feature list
    meta = joblib.load(neutralizer_path)
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names = meta["features"]

    print(">> Veriyi yüklüyorum...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # ==============================
    # SADECE TEST DÖNEMİ — OOS BACKTEST
    # ==============================
    if "dataset_split" not in df.columns:
        raise ValueError("master_df içinde dataset_split yok. Master builder'ı doğru çalıştır.")

    before_all = len(df)
    df = df[df["dataset_split"] == "test"].reset_index(drop=True)
    print(f">> Test filtresi: {before_all} -> {len(df)} satır (OOS backtest)")

    if len(df) == 0:
        raise ValueError("Test döneminde hiç satır yok. train_end_date / valid_end_date ayarlarını kontrol et.")

    # Future return ve market future return kontrolü
    required_cols = [FUT_RET_COL, MARKET_FUT_RET_COL] + FACTOR_COLS + [SECTOR_COL]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"{col} kolonu yok. master_df'ine bak.")

    # Sadece future_return dolu satırlar (test döneminin son 10 günü NaN olabilir)
    before = len(df)
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL]).reset_index(drop=True)
    print(f">> FUT_RET ve MARKET_FUT_RET dropna: {before} -> {len(df)} satır")

    if len(df) == 0:
        raise ValueError("Test döneminde future_return / market_future_return dolu satır kalmadı.")

    # WATCHLIST filtresi (opsiyonel)
    if WATCHLIST is not None:
        before = len(df)
        df = df[df[SYMBOL_COL].isin(WATCHLIST)].reset_index(drop=True)
        print(f">> WATCHLIST filtresi: {before} -> {len(df)} satır, "
              f"{df[SYMBOL_COL].nunique()} sembol")

    # Likidite için turnover hesapla (price_close * volume)
    if PRICE_COL not in df.columns or VOLUME_COL not in df.columns:
        raise ValueError(f"Likidite filtresi için {PRICE_COL} ve {VOLUME_COL} kolonları lazım.")
    df["turnover_tl"] = df[PRICE_COL].astype(float) * df[VOLUME_COL].astype(float)

    # Feature kontrolü
    missing_feats = [f for f in feature_names if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Eksik feature(lar) var: {missing_feats[:10]} ...")

    # Feature matrix
    X_all = df[feature_names].copy()
    X_all = X_all.replace([np.inf, -np.inf], np.nan)
    X_all = X_all.fillna(X_all.median())

    # Faktör ve sektör kolonlarını test verisinden çek
    factor_cols_present = [c for c in FACTOR_COLS if c in df.columns]
    if not factor_cols_present:
        raise ValueError(f"Hiçbir FACTOR_COLS kolonunu bulamadım: {FACTOR_COLS}")
    
    factors_test = df[factor_cols_present].reset_index(drop=True)
    sector_test = df[SECTOR_COL].fillna("other").astype(str).reset_index(drop=True)

    print(">> Feature neutralization (sadece TEST dönemi)...")
    # Eğitimdeki neutralizer zaten fit edilmiş durumda, sadece transform kullanıyoruz
    X_all_neutral = neutralizer.transform(X_all, factors=factors_test, sector=sector_test)

    print(">> Model skor üretiyor (TEST satırları)...")
    df["score"] = model.predict_proba(X_all_neutral.values)[:, 1]

    # Tarihleri sırala (trading günleri)
    unique_dates = sorted(df[DATE_COL].unique())
    n_dates = len(unique_dates)

    print(f">> Test döneminde toplam gün sayısı: {n_dates}")
    print(f">> Rebalance adımı (HORIZON): {HORIZON} gün")
    print(f">> TOP_K: {TOP_K}, MIN_TURNOVER_TL: {MIN_TURNOVER_TL:,.0f}, "
          f"ROUNDTRIP_COST: {ROUNDTRIP_COST*100:.2f}%")

    records = []
    idx = 0

    while idx < n_dates:
        dt = unique_dates[idx]
        day_slice = df[df[DATE_COL] == dt]

        # Likidite filtresi
        liquid = day_slice[day_slice["turnover_tl"] >= MIN_TURNOVER_TL]

        if len(liquid) < MIN_STOCKS_PER_DAY:
            # yeterli likit hisse yoksa bu günü pas geç
            idx += 1
            continue

        # Skora göre sırala
        universe = liquid.sort_values("score", ascending=False)

        top = universe.head(TOP_K)

        # Realized nominal 10d getiri
        gross_strat_ret = top[FUT_RET_COL].mean()

        # Benchmark: index'in 10d getirisi (aynı gün için)
        # Genelde tüm satırlarda aynı olmalı, ortalama alıyoruz
        mkt_ret = universe[MARKET_FUT_RET_COL].mean()

        # Transaction cost + slippage (round-trip)
        net_strat_ret = gross_strat_ret - ROUNDTRIP_COST

        # Alpha = strateji - benchmark
        alpha_ret = net_strat_ret - mkt_ret

        hit_rate = (top[FUT_RET_COL] > 0).mean()
        alpha_hit = (alpha_ret > 0).astype(float)  # tek sayı aslında

        records.append({
            "rebalance_date": dt,
            "n_universe": len(universe),
            "n_liquid": len(liquid),
            "strategy_gross_ret": gross_strat_ret,
            "strategy_net_ret": net_strat_ret,
            "market_ret": mkt_ret,
            "alpha_ret": alpha_ret,
            "hit_rate_nominal": hit_rate,
            "alpha_positive": alpha_hit,
        })

        # Bir sonraki trade: HORIZON gün sonrasına zıpla (overlap yok)
        idx += HORIZON

    if not records:
        raise ValueError("Hiç trade oluşmadı. Muhtemelen filtreler çok sıkı veya test dönemi çok kısa.")

    bt = pd.DataFrame(records).sort_values("rebalance_date").reset_index(drop=True)

    # Equity curves
    bt["strategy_equity"] = (1 + bt["strategy_net_ret"]).cumprod()
    bt["market_equity"] = (1 + bt["market_ret"]).cumprod()
    bt["alpha_equity"] = (1 + bt["alpha_ret"]).cumprod()

    # Özet metrikler
    mean_strat = bt["strategy_net_ret"].mean()
    mean_mkt = bt["market_ret"].mean()
    mean_alpha = bt["alpha_ret"].mean()

    std_strat = bt["strategy_net_ret"].std()
    std_alpha = bt["alpha_ret"].std()

    sharpe_strat = mean_strat / (std_strat + 1e-9)
    sharpe_alpha = mean_alpha / (std_alpha + 1e-9)

    lift_mean = (mean_strat / mean_mkt) if mean_mkt != 0 else np.nan

    print("\n===== REALISTIC NON-OVERLAP ALPHA BACKTEST ÖZET (TEST ONLY) =====")
    print(f"Trade sayısı                        : {len(bt)}")
    print(f"Ortalama strateji NET getirisi      : {mean_strat:.4f}")
    print(f"Ortalama endeks getirisi            : {mean_mkt:.4f}")
    print(f"Ortalama alpha (net - index)        : {mean_alpha:.4f}")
    print(f"Lift (mean_strat / mean_mkt)        : {lift_mean:.2f}")
    print(f"Sharpe (strateji, trade bazlı)      : {sharpe_strat:.2f}")
    print(f"Sharpe (alpha, trade bazlı)         : {sharpe_alpha:.2f}")
    print(f"Nominal hit rate (TOP {TOP_K})      : {bt['hit_rate_nominal'].mean():.2f}")
    print(f"Alpha>0 oranı                       : {bt['alpha_positive'].mean():.2f}")

    # Kaydet
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(BACKTEST_DIR, f"backtest_alpha_nonoverlap_realistic_{ts}.csv")
    bt.to_csv(out_csv, index=False)
    print(f"\nCSV kaydedildi: {out_csv}")

    # Equity curve plot
    plt.figure(figsize=(10, 5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy (Index + Alpha, net)")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Index (Benchmark)")
    plt.plot(bt["rebalance_date"], bt["alpha_equity"], label="Alpha only (excess)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return (1 = flat)")
    plt.title(f"ALPHA Equity Curve (TOP {TOP_K} / {HORIZON}d, non-overlap, realistic, TEST only)")
    plt.legend()
    plt.tight_layout()
    out_png = os.path.join(BACKTEST_DIR, f"equity_curve_alpha_nonoverlap_realistic_{ts}.png")
    plt.savefig(out_png)
    plt.close()
    print(f"Equity curve PNG kaydedildi: {out_png}")

    print("\nRealistic alpha backtest (TEST ONLY) tamamlandı.")


if __name__ == "__main__":
    main()
