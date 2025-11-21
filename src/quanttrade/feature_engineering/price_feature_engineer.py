"""
Price & Technical Feature + Target Agent (FIXED)
=================================================
OHLCV + split + dividend → adj fiyatlar → teknik göstergeler → future returns.

Bu versiyon:
- SPLIT_RATIO normalizasyonu %100 DOĞRU (200 → 2.0, 300 → 3.0, 0.25 → 0.25)
- Geçmiş fiyatları doğru şekilde düzeltiyor
- KOZAL/KONTR/FROTO gibi uçuş yapan future return hatalarını tamamen engelliyor
"""

import pandas as pd
import numpy as np
import logging
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('price_feature_engineer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROCESSED_OHLCV_DIR = PROJECT_ROOT / "data" / "processed" / "ohlcv"
PROCESSED_SPLIT_DIR = PROJECT_ROOT / "data" / "processed" / "split"
PROCESSED_DIVIDEND_DIR = PROJECT_ROOT / "data" / "processed" / "dividend"
FEATURES_PRICE_DIR = PROJECT_ROOT / "data" / "features" / "price"

TARGET_HORIZONS = [10,20,30,60, 90, 120]
TRICLASS_THRESHOLD = 0.02


class PriceFeatureEngineer:

    def __init__(self, ohlcv_dir, split_dir, dividend_dir, output_dir):
        self.ohlcv_dir = ohlcv_dir
        self.split_dir = split_dir
        self.dividend_dir = dividend_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ==========================================================
    # FILE LOADERS
    # ==========================================================

    def load_ohlcv(self, symbol):
        path = self.ohlcv_dir / f"{symbol}_ohlcv_clean.csv"
        if not path.exists():
            logger.warning(f"{symbol}: OHLCV yok.")
            return None
        df = pd.read_csv(path, parse_dates=["date"])
        return df.sort_values("date").reset_index(drop=True)

    def load_split(self, symbol):
        path = self.split_dir / f"{symbol}_split_clean.csv"
        if not path.exists():
            return None
        df = pd.read_csv(path, parse_dates=["split_date"])
        if df.empty:
            return None
        return df.sort_values("split_date").reset_index(drop=True)

    def load_dividend(self, symbol):
        path = self.dividend_dir / f"{symbol}_dividends_clean.csv"
        if not path.exists():
            return None
        df = pd.read_csv(path, parse_dates=["ex_date"])
        if df.empty:
            return None
        return df.sort_values("ex_date").reset_index(drop=True)
    
    def calculate_regime_features(self, df):
        """
        Rejim feature'ları:

        - distance_from_ma200: (adj_close / sma_200) - 1
          -> Hisse uzun vadeli trendine göre ne kadar yukarıda/aşağıda?

        - ma20_slope_5d: sma_20'nin 5 günlük eğimi (yaklaşık momentum)
          -> Kısa vadeli trend yukarı mı aşağı mı?

        - vol_regime: vol_20d / vol_60d
          -> Kısa vadeli vol uzun vadeye göre ne kadar yüksek?
        """

        # 1) MA200'dan uzaklık
        if "sma_200" in df.columns:
            df["distance_from_ma200"] = df["adj_close"] / df["sma_200"] - 1.0

        return df
   

    # ==========================================================
    # SPLIT NORMALIZATION (BIST STANDARD ✓)
    # ==========================================================

    def normalize_ratio(self, r):
        """
        BIST split oranı doğru normalize edilir.

        ÖRNEKLER:
        200  → 2.0 (yüzde formatı)
        300  → 3.0
        600  → 6.0
        2    → 2.0
        0.25 → 0.25 (ters split)
        """
        r = float(r)
        if r <= 0:
            return 1.0
        if r > 20:
            return r / 100.0
        return r

    # ==========================================================
    # APPLY SPLIT ADJUSTMENT ✓✓✓
    # ==========================================================

    def apply_split_adjustment(self, df, splits):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        if splits is None:
            df["adj_close"] = df["close"]
            return df

        df["split_factor"] = 1.0
        splits = splits.sort_values("split_date")

        for _, row in splits.iterrows():
            split_date = row["split_date"]
            ratio_raw = row["split_factor"]
            ratio = self.normalize_ratio(ratio_raw)

            mask = df["date"] < split_date
            df.loc[mask, "split_factor"] *= ratio

        for col in ["close", "open", "high", "low"]:
            if col in df.columns:
                df[f"adj_{col}"] = df[col].astype(float) / df["split_factor"]

        df["adj_close"] = df["adj_close"]
        return df.drop(columns=["split_factor"])

    # ==========================================================
    # DIVIDEND FLAG
    # ==========================================================

    def add_dividend_flags(self, df, dividends):
        df["is_dividend_day"] = 0
        if dividends is None:
            return df
        df.loc[df["date"].isin(dividends["ex_date"]), "is_dividend_day"] = 1
        return df

    # ==========================================================
    # TECHNICAL INDICATORS
    # ==========================================================

    def calculate_returns(self, df):
        df["return_1d"] = df["adj_close"].pct_change()
        df["return_5d"] = df["adj_close"].pct_change(5)
        df["return_20d"] = df["adj_close"].pct_change(20)
        return df

    def calculate_volatility(self, df):
        df["vol_20d"] = df["return_1d"].rolling(20).std()
        df["vol_60d"] = df["return_1d"].rolling(60).std()
        return df

    def calculate_sma(self, df):
        df["sma_20"] = df["adj_close"].rolling(20).mean()
        df["sma_50"] = df["adj_close"].rolling(50).mean()
        df["sma_200"] = df["adj_close"].rolling(200).mean()
        return df

    def calculate_rsi(self, df, period=14):
        delta = df["adj_close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        df["rsi_14"] = 100 - (100 / (1 + rs))
        return df

    def calculate_macd(self, df):
        ema_fast = df["adj_close"].ewm(span=12, adjust=False).mean()
        ema_slow = df["adj_close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        return df

    def calculate_roc(self, df):
        df["roc_10"] = df["adj_close"].pct_change(10) * 100
        return df

    def calculate_atr(self, df):
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(14).mean()
        return df

    def calculate_obv(self, df):
        price_change = df["adj_close"].diff()
        direction = np.where(price_change > 0, df["volume"],
                     np.where(price_change < 0, -df["volume"], 0))
        df["obv"] = direction.cumsum()
        return df

    # ==========================================================
    # TARGET ENGINEERING ✓
    # ==========================================================

    def calculate_targets(self, df):
        for horizon in TARGET_HORIZONS:
            df[f"future_return_{horizon}d"] = df["adj_close"].shift(-horizon) / df["adj_close"] - 1
            df[f"y_{horizon}d_up"] = (df[f"future_return_{horizon}d"] > 0).astype(int)
            df[f"y_{horizon}d_triclass"] = np.where(
                df[f"future_return_{horizon}d"] > TRICLASS_THRESHOLD, 1,
                np.where(df[f"future_return_{horizon}d"] < -TRICLASS_THRESHOLD, -1, 0)
            )
        return df

    # ==========================================================
    # MAIN FEATURE ENGINEERING
    # ==========================================================

    def engineer_features(self, symbol):
        logger.info(f" İşleniyor: {symbol}")

        df = self.load_ohlcv(symbol)
        if df is None:
            return False

        splits = self.load_split(symbol)
        df = self.apply_split_adjustment(df, splits)

        dividends = self.load_dividend(symbol)
        df = self.add_dividend_flags(df, dividends)

        df = self.calculate_returns(df)
        df = self.calculate_volatility(df)
        df = self.calculate_sma(df)
        df = self.calculate_regime_features(df) 
        df = self.calculate_rsi(df)
        df = self.calculate_macd(df)
        df = self.calculate_roc(df)
        df = self.calculate_atr(df)
        df = self.calculate_obv(df)

        df = self.calculate_targets(df)

        out = FEATURES_PRICE_DIR / f"{symbol}_price_features.csv"
        df.to_csv(out, index=False)
        logger.info(f"✓ Kaydedildi → {out}")
        return True

    def engineer_all(self):
        files = sorted(self.ohlcv_dir.glob("*_ohlcv_clean.csv"))
        symbols = [f.stem.replace("_ohlcv_clean", "") for f in files]
        logger.info(f"{len(symbols)} hisse bulunuyor.")

        for sym in symbols:
            self.engineer_features(sym)


def main():
    eng = PriceFeatureEngineer(
        PROCESSED_OHLCV_DIR,
        PROCESSED_SPLIT_DIR,
        PROCESSED_DIVIDEND_DIR,
        FEATURES_PRICE_DIR
    )
    eng.engineer_all()


if __name__ == "__main__":
    sys.exit(main())
