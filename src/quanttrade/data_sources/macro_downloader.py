"""
Macro Downloader - EVDS makro veri indirme script'i

Bu script doğrudan komut satırından çalıştırılabilir:
    python macro_downloader.py

veya başka bir modülden import edilip kullanılabilir:
    from quanttrade.data_sources.macro_downloader import main
    main()
"""

import sys
import logging
from pathlib import Path

# Proje kök dizinini Python path'e ekle
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quanttrade.data_sources.evds_client import EVDSClient


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    EVDS'ten varsayılan makro verileri çeker ve kaydeder.
    
    Bu fonksiyon:
    1. EVDSClient nesnesi oluşturur
    2. settings.toml'da tanımlı serileri çeker
    3. data/raw/macro/evds_macro_daily.csv dosyasına kaydeder
    4. İşlem sonucunu terminale yazdırır
    
    Returns:
        int: Başarılı ise 0, hata varsa 1
    """
    try:
        logger.info("=" * 60)
        logger.info("QuantTrade - EVDS Makro Veri İndirme Başlatılıyor")
        logger.info("=" * 60)
        
        # EVDS client oluştur
        logger.info("EVDS Client oluşturuluyor...")
        client = EVDSClient()
        
        # Varsayılan makro verileri çek ve kaydet
        logger.info("Makro veriler çekiliyor...")
        output_path = client.fetch_and_save_default_macro()
        
        if output_path:
            logger.info("=" * 60)
            logger.info("✓ İŞLEM BAŞARILI")
            logger.info(f"✓ Veriler kaydedildi: {output_path}")
            logger.info("=" * 60)
            return 0
        else:
            logger.warning("Veri çekilemedi veya kaydedilemedi")
            return 1
            
    except ImportError as e:
        logger.error(
            f"Gerekli paketler kurulu değil: {e}\n"
            "Lütfen 'pip install -r requirements.txt' komutunu çalıştırın"
        )
        return 1
    
    except ValueError as e:
        logger.error(f"Konfigürasyon hatası: {e}")
        logger.error(
            "Lütfen .env ve config/settings.toml dosyalarını kontrol edin"
        )
        return 1
    
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
