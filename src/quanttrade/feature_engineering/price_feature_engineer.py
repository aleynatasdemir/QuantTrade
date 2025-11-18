"""
Price & Technical Feature + Target Agent
=========================================
OHLCV, dividend, split verilerinden fiyat bazlı özellikler, teknik göstergeler
ve hedef değişkenler üretir.

Görev:
- Corporate action adjustments (adj_close)
- Return & volatility features
- Teknik indikatörler (RSI, MACD, SMA, ATR, OBV)
- Target engineering (future returns, classification labels)

Kullanım:
    python price_feature_engineer.py
"""

import pandas as pd
import numpy as np
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('price_feature_engineer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Proje dizinleri
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROCESSED_OHLCV_DIR = PROJECT_ROOT / "data" / "processed" / "ohlcv"
PROCESSED_SPLIT_DIR = PROJECT_ROOT / "data" / "processed" / "split"
PROCESSED_DIVIDEND_DIR = PROJECT_ROOT / "data" / "processed" / "dividend"
FEATURES_PRICE_DIR = PROJECT_ROOT / "data" / "features" / "price"

# Target engineering parametreleri
TARGET_HORIZONS = [5, 20]  # Gün sayıları
TRICLASS_THRESHOLD = 0.02  # %2 eşiği


class PriceFeatureEngineer:
    """Fiyat bazlı özellikler ve hedef değişkenler üretir."""
    
    def __init__(
        self,
        ohlcv_dir: Path,
        split_dir: Path,
        dividend_dir: Path,
        output_dir: Path
    ):
        """
        Args:
            ohlcv_dir: Temiz OHLCV klasörü
            split_dir: Temiz split klasörü
            dividend_dir: Temiz dividend klasörü
            output_dir: Çıktı klasörü
        """
        self.ohlcv_dir = ohlcv_dir
        self.split_dir = split_dir
        self.dividend_dir = dividend_dir
        self.output_dir = output_dir
        
        # Çıktı klasörünü oluştur
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("="*80)
        logger.info("PRICE & TECHNICAL FEATURE + TARGET AGENT")
        logger.info("="*80)
        logger.info(f"OHLCV klasörü: {self.ohlcv_dir}")
        logger.info(f"Split klasörü: {self.split_dir}")
        logger.info(f"Dividend klasörü: {self.dividend_dir}")
        logger.info(f"Çıktı klasörü: {self.output_dir}")
    
    def load_ohlcv(self, symbol: str) -> Optional[pd.DataFrame]:
        """OHLCV verisini yükler."""
        ohlcv_file = self.ohlcv_dir / f"{symbol}_ohlcv_clean.csv"
        
        if not ohlcv_file.exists():
            logger.warning(f"{symbol}: OHLCV dosyası bulunamadı")
            return None
        
        try:
            df = pd.read_csv(ohlcv_file, parse_dates=['date'])
            df = df.sort_values('date').reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"{symbol}: OHLCV yükleme hatası - {e}")
            return None
    
    def load_split(self, symbol: str) -> Optional[pd.DataFrame]:
        """Split verisini yükler."""
        split_file = self.split_dir / f"{symbol}_split_clean.csv"
        
        if not split_file.exists():
            return None
        
        try:
            df = pd.read_csv(split_file, parse_dates=['split_date'])
            if df.empty:
                return None
            df = df.sort_values('split_date').reset_index(drop=True)
            return df
        except Exception as e:
            logger.warning(f"{symbol}: Split yükleme hatası - {e}")
            return None
    
    def load_dividend(self, symbol: str) -> Optional[pd.DataFrame]:
        """Dividend verisini yükler."""
        dividend_file = self.dividend_dir / f"{symbol}_dividends_clean.csv"
        
        if not dividend_file.exists():
            return None
        
        try:
            df = pd.read_csv(dividend_file, parse_dates=['ex_date'])
            if df.empty:
                return None
            df = df.sort_values('ex_date').reset_index(drop=True)
            return df
        except Exception as e:
            logger.warning(f"{symbol}: Dividend yükleme hatası - {e}")
            return None
    
    def apply_split_adjustment(
        self, 
        ohlcv: pd.DataFrame, 
        splits: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Split-adjusted close hesaplar.
        
        Args:
            ohlcv: OHLCV DataFrame
            splits: Split DataFrame (opsiyonel)
        
        Returns:
            pd.DataFrame: adj_close kolonlu OHLCV
        """
        # Split yoksa adj_close = close
        if splits is None or splits.empty:
            ohlcv['adj_close'] = ohlcv['close']
            return ohlcv
        
        # Her tarih için cumulative split factor hesapla
        ohlcv['cumulative_split_factor'] = 1.0
        
        for _, split_row in splits.iterrows():
            split_date = split_row['split_date']
            cumulative_factor = split_row['cumulative_split_factor']
            
            # Split tarihinden önceki tüm fiyatları düzelt
            mask = ohlcv['date'] < split_date
            ohlcv.loc[mask, 'cumulative_split_factor'] = cumulative_factor
        
        # Adjusted close hesapla
        ohlcv['adj_close'] = ohlcv['close'] / ohlcv['cumulative_split_factor']
        
        # Geçici kolonu sil
        ohlcv = ohlcv.drop('cumulative_split_factor', axis=1)
        
        return ohlcv
    
    def add_dividend_flags(
        self,
        ohlcv: pd.DataFrame,
        dividends: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Temettü günlerini flag olarak ekler.
        
        Args:
            ohlcv: OHLCV DataFrame
            dividends: Dividend DataFrame (opsiyonel)
        
        Returns:
            pd.DataFrame: is_dividend_day kolonlu OHLCV
        """
        ohlcv['is_dividend_day'] = 0
        
        if dividends is None or dividends.empty:
            return ohlcv
        
        # Temettü tarihlerini işaretle
        for _, div_row in dividends.iterrows():
            ex_date = div_row['ex_date']
            mask = ohlcv['date'] == ex_date
            ohlcv.loc[mask, 'is_dividend_day'] = 1
        
        return ohlcv
    
    def calculate_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return özelliklerini hesaplar."""
        # Günlük return (adj_close bazlı)
        df['return_1d'] = df['adj_close'].pct_change(1)
        df['return_5d'] = df['adj_close'].pct_change(5)
        df['return_20d'] = df['adj_close'].pct_change(20)
        
        return df
    
    def calculate_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volatilite özelliklerini hesaplar."""
        # Rolling volatility (return_1d üzerinden)
        df['vol_20d'] = df['return_1d'].rolling(20).std()
        df['vol_60d'] = df['return_1d'].rolling(60).std()
        
        return df
    
    def calculate_sma(self, df: pd.DataFrame) -> pd.DataFrame:
        """Simple Moving Average hesaplar."""
        df['sma_20'] = df['adj_close'].rolling(20).mean()
        df['sma_50'] = df['adj_close'].rolling(50).mean()
        df['sma_200'] = df['adj_close'].rolling(200).mean()
        
        return df
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Relative Strength Index hesaplar."""
        # Fiyat değişimleri
        delta = df['adj_close'].diff()
        
        # Kazanç ve kayıplar
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Rolling ortalamalar
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        # RS ve RSI
        rs = avg_gain / avg_loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> pd.DataFrame:
        """MACD hesaplar."""
        # EMA'lar
        ema_fast = df['adj_close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['adj_close'].ewm(span=slow, adjust=False).mean()
        
        # MACD line
        df['macd'] = ema_fast - ema_slow
        
        # Signal line
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        
        # MACD histogram
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        return df
    
    def calculate_roc(self, df: pd.DataFrame, period: int = 10) -> pd.DataFrame:
        """Rate of Change hesaplar."""
        df['roc_10'] = df['adj_close'].pct_change(period) * 100
        
        return df
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Average True Range hesaplar."""
        # True Range hesapla
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # ATR
        df['atr_14'] = tr.rolling(period).mean()
        
        return df
    
    def calculate_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """On-Balance Volume hesaplar."""
        # Fiyat değişimi yönü
        price_change = df['adj_close'].diff()
        
        # Volume yönü
        volume_direction = np.where(price_change > 0, df['volume'],
                                   np.where(price_change < 0, -df['volume'], 0))
        
        # Kümülatif OBV
        df['obv'] = volume_direction.cumsum()
        
        return df
    
    def calculate_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Hedef değişkenleri hesaplar."""
        # Future returns
        for horizon in TARGET_HORIZONS:
            col_name = f'future_return_{horizon}d'
            df[col_name] = df['adj_close'].shift(-horizon) / df['adj_close'] - 1
            
            # Binary classification
            binary_col = f'y_{horizon}d_up'
            df[binary_col] = (df[col_name] > 0).astype(int)
            
            # Tri-class classification
            triclass_col = f'y_{horizon}d_triclass'
            df[triclass_col] = np.where(
                df[col_name] > TRICLASS_THRESHOLD, 1,  # Buy
                np.where(
                    df[col_name] < -TRICLASS_THRESHOLD, -1,  # Sell
                    0  # Hold
                )
            )
        
        return df
    
    def engineer_features(self, symbol: str) -> bool:
        """
        Tek bir hisse için tüm özellikleri üretir.
        
        Args:
            symbol: Hisse sembolü
        
        Returns:
            bool: Başarılı ise True
        """
        logger.info(f"İşleniyor: {symbol}")
        
        try:
            # 1. OHLCV yükle
            ohlcv = self.load_ohlcv(symbol)
            if ohlcv is None or ohlcv.empty:
                logger.warning(f"{symbol}: OHLCV verisi yok")
                return False
            
            original_rows = len(ohlcv)
            
            # 2. Split yükle ve adj_close hesapla
            splits = self.load_split(symbol)
            ohlcv = self.apply_split_adjustment(ohlcv, splits)
            
            split_count = len(splits) if splits is not None else 0
            logger.debug(f"{symbol}: {split_count} split uygulandı")
            
            # 3. Dividend flag ekle
            dividends = self.load_dividend(symbol)
            ohlcv = self.add_dividend_flags(ohlcv, dividends)
            
            # 4. Return & Volatility
            ohlcv = self.calculate_returns(ohlcv)
            ohlcv = self.calculate_volatility(ohlcv)
            
            # 5. Teknik İndikatörler
            ohlcv = self.calculate_sma(ohlcv)
            ohlcv = self.calculate_rsi(ohlcv)
            ohlcv = self.calculate_macd(ohlcv)
            ohlcv = self.calculate_roc(ohlcv)
            ohlcv = self.calculate_atr(ohlcv)
            ohlcv = self.calculate_obv(ohlcv)
            
            # 6. Target Engineering
            ohlcv = self.calculate_targets(ohlcv)
            
            # 7. NaN kontrolü
            # İlk N satır (rolling window'lar nedeniyle) NaN olabilir, ama bu normal
            valid_rows = ohlcv['adj_close'].notna().sum()
            
            # 8. Çıktı dosyası
            output_file = self.output_dir / f"{symbol}_price_features.csv"
            ohlcv.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(
                f"✓ {symbol}: {len(ohlcv)} satır kaydedildi "
                f"({original_rows - valid_rows} NaN) "
                f"[{ohlcv['date'].min().date()} - {ohlcv['date'].max().date()}]"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Hata - {e}", exc_info=True)
            return False
    
    def engineer_all(self) -> None:
        """Tüm hisseler için özellikleri üretir."""
        # OHLCV dosyalarını listele
        ohlcv_files = sorted(self.ohlcv_dir.glob("*_ohlcv_clean.csv"))
        
        if not ohlcv_files:
            logger.warning(f"OHLCV klasöründe dosya bulunamadı: {self.ohlcv_dir}")
            return
        
        # Sembolleri çıkar
        symbols = [f.stem.replace('_ohlcv_clean', '') for f in ohlcv_files]
        
        logger.info(f"Toplam {len(symbols)} hisse bulundu")
        logger.info("="*80)
        
        # İstatistikler
        success_count = 0
        error_count = 0
        errors = []
        
        # Her hisse için işle
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] {symbol}")
            
            if self.engineer_features(symbol):
                success_count += 1
            else:
                error_count += 1
                errors.append(symbol)
        
        # Özet rapor
        logger.info("="*80)
        logger.info("FEATURE ENGİNEERİNG TAMAMLANDI")
        logger.info("="*80)
        logger.info(f"✓ Başarılı: {success_count}/{len(symbols)}")
        logger.info(f"✗ Hata: {error_count}/{len(symbols)}")
        
        if errors:
            logger.info("\nHatalı Hisseler:")
            for error_symbol in errors:
                logger.info(f"  - {error_symbol}")
        
        logger.info(f"\nFeature'lar: {self.output_dir}")
        logger.info("="*80)
        
        # Örnek çıktı göster
        if success_count > 0:
            sample_symbol = symbols[0]
            sample_file = self.output_dir / f"{sample_symbol}_price_features.csv"
            if sample_file.exists():
                df_sample = pd.read_csv(sample_file, nrows=5)
                logger.info(f"\nÖrnek çıktı ({sample_symbol}):")
                logger.info(f"Kolonlar ({len(df_sample.columns)}): {list(df_sample.columns)}")


def main():
    """Ana fonksiyon"""
    logger.info("Price & Technical Feature Engineer başlatılıyor...")
    
    # Klasörleri kontrol et
    if not PROCESSED_OHLCV_DIR.exists():
        logger.error(f"OHLCV klasörü bulunamadı: {PROCESSED_OHLCV_DIR}")
        logger.error("Lütfen önce ohlcv_cleaner.py çalıştırın")
        return 1
    
    # Engineer'ı oluştur ve çalıştır
    engineer = PriceFeatureEngineer(
        ohlcv_dir=PROCESSED_OHLCV_DIR,
        split_dir=PROCESSED_SPLIT_DIR,
        dividend_dir=PROCESSED_DIVIDEND_DIR,
        output_dir=FEATURES_PRICE_DIR
    )
    engineer.engineer_all()
    
    logger.info("\nİşlem tamamlandı!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
