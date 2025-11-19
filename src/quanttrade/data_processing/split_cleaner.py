"""
Split Verisi Temizleyici Agent
===============================
Ham split/bölünme verilerini temizler, normalize eder ve kümülatif faktör hesaplar.

Görev:
- data/raw/split_ratio/ altındaki split CSV'lerini okur
- Split tarih ve oranlarını normalize eder
- Kümülatif split faktörü hesaplar
- Temiz verileri data/processed/split/ altına yazar

Kullanım:
    python split_cleaner.py
"""

import pandas as pd
import numpy as np
import logging
import sys
import re
from pathlib import Path
from typing import Optional

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('split_cleaner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Proje dizinleri
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_SPLIT_DIR = PROJECT_ROOT / "data" / "raw" / "split_ratio"
PROCESSED_SPLIT_DIR = PROJECT_ROOT / "data" / "processed" / "split"

# Standart kolon isimleri
STANDARD_COLUMNS = ['symbol', 'split_date', 'split_factor', 'cumulative_split_factor']


class SplitCleaner:
    """Split/bölünme verilerini temizler ve normalize eder."""
    
    def __init__(self, raw_dir: Path, processed_dir: Path):
        """
        Args:
            raw_dir: Ham veri klasörü
            processed_dir: İşlenmiş veri klasörü
        """
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        
        # Çıktı klasörünü oluştur
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("="*80)
        logger.info("SPLIT VERİSİ TEMİZLEYİCİ AGENT")
        logger.info("="*80)
        logger.info(f"Ham veri klasörü: {self.raw_dir}")
        logger.info(f"İşlenmiş veri klasörü: {self.processed_dir}")
    
    def extract_symbol_from_filename(self, filename: str) -> Optional[str]:
        """
        Dosya adından sembol çıkarır.
        
        Args:
            filename: Dosya adı (örn: ASELS_split.csv)
        
        Returns:
            str: Sembol (örn: ASELS) veya None
        """
        try:
            # _split.csv kısmını kaldır
            symbol = filename.replace('_split.csv', '').upper().strip()
            return symbol
        except Exception as e:
            logger.warning(f"Sembol çıkarılamadı ({filename}): {e}")
            return None
    
    def parse_split_ratio(self, ratio_str, tip_kodu=None, bedelsiz_tm_oran=None) -> Optional[float]:
        """
        Split oranını parse eder ve normalize eder.
        
        Split faktörü mantığı:
        - Bedelsiz sermaye artırımı (tip_kodu=2,9): %100 → 2.0 (2 kat)
        - Bölünme: 1/2 → 2.0 (her hisse 2'ye bölünür)
        - Nakit temettü (tip_kodu=4): split_factor = 1.0 (bölünme yok)
        
        Args:
            ratio_str: SPLIT_RATIO kolonu
            tip_kodu: SHHE_TIP_KODU (2=bedelsiz, 4=nakit, 9=bedelsiz temettü)
            bedelsiz_tm_oran: SHHE_BDSZ_TM_ORAN (bedelsiz temettü oranı, %100=100)
        
        Returns:
            float: Split faktörü veya None
        """
        # Nakit temettü: split yok
        if tip_kodu == 4:
            return 1.0
        
        # SPLIT_RATIO sütunu varsa önce onu dene
        if ratio_str is not None and not pd.isna(ratio_str):
            try:
                # Direkt float değer
                ratio = float(ratio_str)
                if ratio > 0:
                    return ratio
            except (ValueError, TypeError):
                pass
        
        # Bedelsiz temettü oranından hesapla
        # SHHE_BDSZ_TM_ORAN: %100 → 100, split_factor = 2.0
        if bedelsiz_tm_oran is not None and not pd.isna(bedelsiz_tm_oran):
            try:
                bedelsiz_oran = float(bedelsiz_tm_oran)
                if bedelsiz_oran > 0:
                    # %100 bedelsiz = 2x sermaye = 2.0 split
                    # %50 bedelsiz = 1.5x sermaye = 1.5 split
                    split_factor = 1.0 + (bedelsiz_oran / 100.0)
                    return split_factor
            except (ValueError, TypeError):
                pass
        
        # Parse edilemedi
        return None
    
    def clean_file(self, file_path: Path) -> bool:
        """
        Tek bir split dosyasını temizler.
        
        Args:
            file_path: Ham CSV dosyasının yolu
        
        Returns:
            bool: Başarılı ise True
        """
        filename = file_path.name
        symbol = self.extract_symbol_from_filename(filename)
        
        if not symbol:
            logger.error(f"Sembol çıkarılamadı: {filename}")
            return False
        
        logger.info(f"İşleniyor: {symbol} ({filename})")
        
        try:
            # CSV'yi oku
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            if df.empty:
                logger.warning(f"{symbol}: Boş dosya")
                return False
            
            original_rows = len(df)
            logger.debug(f"{symbol}: {original_rows} satır okundu")
            
            # Gerekli kolonları kontrol et
            required_cols = ['SHHE_TARIH', 'SHHE_TIP_KODU']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                logger.error(f"{symbol}: Eksik kolonlar: {missing_cols}")
                return False
            
            # Sembol ekle
            df['symbol'] = symbol.upper()
            
            # Tarih dönüşümü
            # SHHE_TARIH formatı: 2020-07-17 (string)
            df['split_date'] = pd.to_datetime(df['SHHE_TARIH'], errors='coerce')
            
            # Geçersiz tarihleri filtrele
            before_count = len(df)
            df = df[df['split_date'].notna()].copy()
            after_count = len(df)
            
            if before_count > after_count:
                logger.debug(f"{symbol}: {before_count - after_count} adet geçersiz tarih silindi")
            
            if df.empty:
                logger.warning(f"{symbol}: Tüm tarihler geçersiz")
                return False
            
            # Split factor hesapla
            df['split_factor'] = df.apply(
                lambda row: self.parse_split_ratio(
                    ratio_str=row.get('SPLIT_RATIO'),
                    tip_kodu=row.get('SHHE_TIP_KODU'),
                    bedelsiz_tm_oran=row.get('SHHE_BDSZ_TM_ORAN')
                ),
                axis=1
            )
            
            # Geçersiz split_factor'ları sil (None olanlar)
            # NOT: split_factor=1.0 (nakit temettü) de tutuyoruz, çünkü kayıt amaçlı önemli
            before_count = len(df)
            df = df[df['split_factor'].notna()].copy()
            after_count = len(df)
            
            if before_count > after_count:
                logger.debug(f"{symbol}: {before_count - after_count} adet geçersiz kayıt filtrelendi")
            
            if df.empty:
                logger.info(f"{symbol}: Hiç split bulunamadı (sadece nakit temettü var)")
                # Boş dosya oluştur
                empty_df = pd.DataFrame(columns=STANDARD_COLUMNS)
                output_file = self.processed_dir / f"{symbol}_split_clean.csv"
                empty_df.to_csv(output_file, index=False, encoding='utf-8')
                logger.info(f"✓ {symbol}: Boş dosya kaydedildi (split yok)")
                return True
            
            # Tarihe göre sırala (eskiden yeniye)
            df = df.sort_values('split_date').reset_index(drop=True)
            
            # Kümülatif split faktörü hesapla
            # cumulative_split_factor: başlangıç 1.0, her split'te çarpılır
            df['cumulative_split_factor'] = df['split_factor'].cumprod()
            
            # Sadece gerekli kolonları seç
            df = df[STANDARD_COLUMNS].copy()
            
            # Çıktı dosyası
            output_file = self.processed_dir / f"{symbol}_split_clean.csv"
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(
                f"✓ {symbol}: {len(df)} split kaydedildi "
                f"[{df['split_date'].min().date()} - {df['split_date'].max().date()}]"
            )
            
            # Split detaylarını göster
            for _, row in df.iterrows():
                logger.debug(
                    f"  {row['split_date'].date()}: "
                    f"factor={row['split_factor']:.2f}, "
                    f"cumulative={row['cumulative_split_factor']:.2f}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"✗ {symbol}: Hata - {e}", exc_info=True)
            return False
    
    def clean_all(self) -> None:
        """Tüm split dosyalarını temizler."""
        # CSV dosyalarını listele
        csv_files = sorted(self.raw_dir.glob("*_split.csv"))
        
        if not csv_files:
            logger.warning(f"Ham veri klasöründe split CSV dosyası bulunamadı: {self.raw_dir}")
            return
        
        logger.info(f"Toplam {len(csv_files)} dosya bulundu")
        logger.info("="*80)
        
        # İstatistikler
        success_count = 0
        error_count = 0
        split_count = 0
        no_split_count = 0
        errors = []
        
        # Her dosyayı işle
        for i, file_path in enumerate(csv_files, 1):
            logger.info(f"[{i}/{len(csv_files)}] {file_path.name}")
            
            if self.clean_file(file_path):
                success_count += 1
                # Split sayısını kontrol et
                output_file = self.processed_dir / f"{self.extract_symbol_from_filename(file_path.name)}_split_clean.csv"
                if output_file.exists():
                    df_check = pd.read_csv(output_file)
                    if len(df_check) > 0:
                        split_count += 1
                    else:
                        no_split_count += 1
            else:
                error_count += 1
                errors.append(file_path.name)
        
        # Özet rapor
        logger.info("="*80)
        logger.info("TEMİZLEME TAMAMLANDI")
        logger.info("="*80)
        logger.info(f"✓ Başarılı: {success_count}/{len(csv_files)}")
        logger.info(f"✗ Hata: {error_count}/{len(csv_files)}")
        logger.info(f"Split olan hisse: {split_count}")
        logger.info(f"Split olmayan hisse: {no_split_count}")
        
        if errors:
            logger.info("\nHatalı Dosyalar:")
            for error_file in errors:
                logger.info(f"  - {error_file}")
        
        logger.info(f"\nTemiz veriler: {self.processed_dir}")
        logger.info("="*80)


def main():
    """Ana fonksiyon"""
    logger.info("Split Temizleyici Agent başlatılıyor...")
    
    # Klasörleri kontrol et
    if not RAW_SPLIT_DIR.exists():
        logger.error(f"Ham veri klasörü bulunamadı: {RAW_SPLIT_DIR}")
        logger.error("Lütfen önce split verilerini indirin")
        return 1
    
    # Cleaner'ı oluştur ve çalıştır
    cleaner = SplitCleaner(raw_dir=RAW_SPLIT_DIR, processed_dir=PROCESSED_SPLIT_DIR)
    cleaner.clean_all()
    
    logger.info("\nİşlem tamamlandı!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
