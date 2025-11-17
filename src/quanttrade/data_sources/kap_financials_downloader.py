"""
KAP Financials Downloader - Finansal rapor duyurularını indiren script

Bu script KAP'tan finansal rapor duyurularını çeker ve CSV olarak kaydeder.

Kullanım:
    python -m src.quanttrade.data_sources.kap_financials_downloader
    
veya:
    python src/quanttrade/data_sources/kap_financials_downloader.py
"""

import sys
import logging
from pathlib import Path

# Proje kök dizinini Python path'e ekle
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quanttrade.data_sources.kap_client import KapDataClient


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    KAP'tan finansal rapor duyurularını çeker ve CSV olarak kaydeder.
    
    Bu fonksiyon:
    1. KapDataClient nesnesi oluşturur
    2. kap_settings.toml'da tanımlı tüm ticker'lar için finansal rapor duyurularını çeker
    3. Verileri data/raw/kap/financials.csv dosyasına kaydeder
    4. İşlem sonucunu terminale yazdırır
    
    Returns:
        int: Başarılı ise 0, hata varsa 1
    """
    try:
        logger.info("=" * 70)
        logger.info("QuantTrade - KAP Finansal Rapor Duyuruları İndirme")
        logger.info("=" * 70)
        
        # KAP client oluştur
        logger.info("KAP Client oluşturuluyor...")
        client = KapDataClient()
        
        # Tüm ticker'lar için finansal rapor verilerini çek
        logger.info("Finansal rapor duyuruları çekiliyor...")
        logger.info("Bu işlem biraz zaman alabilir, lütfen bekleyin...")
        
        df_all = client.fetch_all_financials_for_all_tickers()
        
        if df_all.empty:
            logger.warning("⚠ Hiç finansal rapor verisi çekilemedi")
            logger.warning("Olası nedenler:")
            logger.warning("  - pykap API çağrısı henüz implement edilmemiş (placeholder modda)")
            logger.warning("  - KAP erişim sorunu")
            logger.warning("  - Ticker kodları yanlış")
            logger.warning("")
            logger.warning("Lütfen kap_client.py içindeki _fetch_disclosures_from_pykap() "
                          "fonksiyonunu pykap dokümantasyonuna göre güncelleyin.")
            return 1
        
        # CSV olarak kaydet
        logger.info("Veriler kaydediliyor...")
        output_path = client.save_financials_csv(df_all)
        
        # Özet bilgi
        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ İŞLEM BAŞARILI - Finansal Rapor Verileri")
        logger.info("=" * 70)
        logger.info(f"✓ Dosya: {output_path}")
        logger.info(f"✓ Toplam kayıt: {len(df_all):,}")
        logger.info(f"✓ Toplam ticker: {df_all['ticker'].nunique()}")
        logger.info("")
        
        # İlk birkaç satırı göster
        if len(df_all) > 0:
            logger.info("İlk 5 kayıt:")
            print(df_all.head().to_string())
            logger.info("")
            
            # Ticker bazında özet
            logger.info("Ticker bazında özet:")
            ticker_counts = df_all['ticker'].value_counts()
            print(ticker_counts.to_string())
        
        logger.info("=" * 70)
        return 0
            
    except ImportError as e:
        logger.error(
            f"Gerekli paketler kurulu değil: {e}\n"
            "Lütfen 'pip install -r requirements.txt' komutunu çalıştırın"
        )
        return 1
    
    except FileNotFoundError as e:
        logger.error(f"Konfigürasyon dosyası bulunamadı: {e}")
        logger.error(
            "Lütfen config/kap_settings.toml dosyasının mevcut olduğundan emin olun"
        )
        return 1
    
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
