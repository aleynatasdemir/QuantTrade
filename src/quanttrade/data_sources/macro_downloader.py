"""
Macro Downloader - EVDS makro veri indirme script'i (INCREMENTAL MOD)

INCREMENTAL LOGIC:
- Mevcut CSV dosyasındaki son tarihe bakar
- Sadece eksik günleri EVDS'ten çeker
- Eski veriyle birleştirir

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
    EVDS'ten varsayılan makro verileri INCREMENTAL olarak çeker ve kaydeder.
    
    INCREMENTAL DAVRANIŞI:
    - Mevcut dosyadaki son tarihe bakar
    - Sadece eksik günleri çeker
    - Güncel ise API çağrısı yapmaz
    
    Returns:
        int: Başarılı ise 0, hata varsa 1
    """
    try:
        logger.info("=" * 60)
        logger.info("QuantTrade - EVDS Makro Veri İndirme (INCREMENTAL MOD)")
        logger.info("=" * 60)
        
        # EVDS client oluştur
        logger.info("EVDS Client oluşturuluyor...")
        client = EVDSClient()
        
        # Varsayılan makro verileri INCREMENTAL olarak çek ve kaydet
        logger.info("Makro veriler çekiliyor (incremental)...")
        output_path = client.fetch_and_save_default_macro(incremental=True)
        
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
