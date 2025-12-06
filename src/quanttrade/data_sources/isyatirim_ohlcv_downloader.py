"""
İş Yatırım OHLCV Downloader - Günlük OHLCV verilerini INCREMENTAL olarak indiren script

Bu script İş Yatırım sitesinden BIST hisseleri için OHLCV verilerini çeker
ve CSV dosyalarına kaydeder.

INCREMENTAL LOGIC:
- Her sembol için mevcut dosyaya bakar
- Sadece eksik günleri çeker
- API yükünü minimize eder

Kullanım:
    python -m src.quanttrade.data_sources.isyatirim_ohlcv_downloader
    
veya:
    python src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Proje kök dizinini Python path'e ekle
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quanttrade.data_sources.isyatirim_ohlcv import fetch_ohlcv_from_isyatirim
from quanttrade.config import ROOT_DIR, get_stock_symbols, get_stock_date_range


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> int:
    """
    İş Yatırım'dan OHLCV verilerini INCREMENTAL olarak çeker ve CSV dosyalarına kaydeder.
    Sembol listesi ve tarih aralığı config/settings.toml'dan okunur.
    
    INCREMENTAL DAVRANIŞI:
    - Mevcut dosyası olan semboller için son tarihten itibaren veri çeker
    - Yeni semboller için full aralık çeker
    - Güncel semboller atlanır
    
    Returns:
        int: Başarılı ise 0, hata varsa 1
    """
    try:
        # Config'den sembol listesini al
        try:
            symbols = get_stock_symbols()
            start_date, end_date = get_stock_date_range()
            logger.info("✓ Ayarlar config/settings.toml'dan okundu")
        except Exception as e:
            logger.error(f"Config okunamadı: {e}")
            logger.error("Lütfen config/settings.toml dosyasını kontrol edin")
            return 1
        
        if not symbols:
            logger.error("Sembol listesi boş! config/settings.toml dosyasında [stocks] bölümünü kontrol edin")
            return 1
        
        # Çıktı dizini
        output_dir = ROOT_DIR / "data" / "raw" / "ohlcv"
        
        logger.info("="*80)
        logger.info("İŞ YATIRIM OHLCV VERİ ÇEKME (INCREMENTAL MOD)")
        logger.info("="*80)
        logger.info(f"Toplam sembol sayısı: {len(symbols)}")
        logger.info(f"Config tarih aralığı: {start_date} - {end_date}")
        logger.info(f"Çıktı dizini: {output_dir}")
        logger.info(f"İlk 10 sembol: {', '.join(symbols[:10])}")
        if len(symbols) > 10:
            logger.info(f"... ve {len(symbols) - 10} sembol daha")
        logger.info("")
        logger.info("NOT: Her sembol için mevcut veri kontrol edilecek.")
        logger.info("     Sadece eksik günler çekilecek, güncel semboller atlanacak.")
        logger.info("="*80)
        
        # İş Yatırım'dan veri çek (INCREMENTAL)
        fetch_ohlcv_from_isyatirim(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            output_dir=str(output_dir),
            rate_limit_delay=2.0,  # IP ban riski için bekleme
        )
        
        return 0
        
    except ImportError as e:
        logger.error(
            f"Gerekli paketler kurulu değil: {e}\n"
            "Lütfen 'pip install -r requirements.txt' komutunu çalıştırın"
        )
        return 1
    
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
