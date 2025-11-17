"""
İş Yatırım OHLCV Downloader - Günlük OHLCV verilerini indiren script

Bu script İş Yatırım sitesinden BIST hisseleri için OHLCV verilerini çeker
ve parquet dosyalarına kaydeder.

Kullanım:
    python -m src.quanttrade.data_sources.isyatirim_ohlcv_downloader
    
veya:
    python src/quanttrade/data_sources/isyatirim_ohlcv_downloader.py
"""

import sys
import logging
from pathlib import Path

# Proje kök dizinini Python path'e ekle
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quanttrade.data_sources.isyatirim_ohlcv import fetch_ohlcv_from_isyatirim
from quanttrade.config import ROOT_DIR


# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> int:
    """
    İş Yatırım'dan OHLCV verilerini çeker ve parquet dosyalarına kaydeder.
    
    Returns:
        int: Başarılı ise 0, hata varsa 1
    """
    try:
        # Çekilecek BIST hisseleri
        # İstediğin sembol listesini buraya ekle
        symbols = [
            # Ağır Endüstri
            "TUPRS",   # Tüpraş
            "EREGL",   # Ereğli Demir Çelik
            "ASELS",   # Aselsan
            "ARCLK",   # Arçelik
            "KRDMD",   # Kardemir
            "TOASO",   # Toros Ağır Sanayii
            "DMSAS",   # Doğuş Müteahhitlik
            
            # Bankalar
            "AKBNK",   # Akbank
            "GARAN",   # Garanti BBVA
            "ISCTR",   # İş Bankası (C)
            "YKBNK",   # Yapı Kredi Bankası
            "HALKB",   # Halk Bankası
            "TCELL",   # Turkcell (T.Mobil)
            "TBNK",    # T.Bankası (Türk Ekonomi Bankası - değişti, kontrol et)
            "SKBNK",   # Şekerbank
            "NYKBN",   # Nuh Çimento
            
            # Perakende & Dağıtım
            "BIMAS",   # BİM Birleşik Mağazalar
            "MGROS",   # Migros
            "CCOLA",   # Coca-Cola İçecek
            "CARSI",   # Carrefoursa (varsa kontrol et)
            
            # Turizm & Otelcilik
            "THYAO",   # Türk Hava Yolları
            "NTHOL",   # Net Turizm
            "AVTUR",   # Avtur Turizm (varsa kontrol et)
            
            # Enerji & Madencilik
            "PETKM",   # Petrol Kimya
            "KOZAL",   # Koç Holding (Alatürk)
            "KCHOL",   # Koç Holding
            "SAHOL",   # Sabancı Holding
            "DOHOL",   # Dış Ticaret
            "ENKAI",   # Enka İnşaat
            "ENJSA",   # Enerjisa
            "INEEL",   # İntelit (Elektrik üreticisi)
            "PGSUS",   # Palsgaard (varsa kontrol et)
            
            # İnşaat & Gayrimenkul
            "SGGYO",   # Sönmez Gayrimenkul
            "ISGYO",   # İskenderun Demir Çelik (GYO)
            "EKGYO",   # Eka Gayrimenkul
            "MPARK",   # Mepet Pazarlama (Mall of Antalya)
            "RSGYO",   # Rota Gayrimenkul
            "ODAS",    # Ödaş (Ege Elektrik)
            "FROTO",   # Froto (Pazarlama Turizm)
            "VGGYO",   # Varlık Gayrimenkul
            "ISGYO",   # İstanbul Gayrimenkul
            
            # Tarım & Gıda
            "ULKER",   # Ülker Bisküvi
            "ALYAG",   # Alyağ (varsa kontrol et)
            "QUAGR",   # Quasar Tarım (varsa kontrol et)
            
            # Kimya & İlaç
            "PIMSA",   # Pınar Süt Ürünleri
            "SASA",    # Sasa Polyester
            "SNGYO",   # Sinpaş Gayrimenkul
            "YAZIC",   # Yazıcıoğlu (varsa kontrol et)
            
            # Tekstil & Giyim
            "GEYZF",   # Geylor (varsa kontrol et)
            "SMART",   # SMARTech (varsa kontrol et)
            
            # Ulaştırma & Lojistik
            "TCELL",   # Turkcell (Communications)
            "TTKOM",   # Türk Telekom
            "TTKUR",   # Türk Telekom Kurumsal
            "VOPAK",   # Vopak (Port Operations)
            
            # Bilgisayar & Teknoloji
            "IPEKE",   # İpek Bilişim (varsa kontrol et)
            "INEEL",   # İntel Elektronik (varsa kontrol et)
            
            # Medya & İletişim
            "DKBNK",   # Dönergip Bank (varsa kontrol et)
            "SNPAM",   # Snap Pazarlama
            
            # Diğer önemli hisseler
            "SISE",    # Şişe Cam
            "WDOEM",   # Wade (varsa kontrol et)
            "ROLO",    # Rolo (varsa kontrol et)
            "GOBNK",   # Göç Bankası (varsa kontrol et)
            "TAVHL",   # Tav Havalimanları
            "TSPOR",   # Trabzonspor (varsa kontrol et)
            "YYLGYO",  # Yön Gayrimenkul
            "ZOREN",   # Zorlubay Tekstil (varsa kontrol et)
            "ZKBNK",   # Ziraat Bankası (varsa kontrol et)
            "TTKOM",   # Türk Telekom
            
            # Eksik kontrol edilecek
            "GUBRF",   # Gübre Endüstrileri
            "GLYHO",   # Galata Ticaret
            "KOZAA",   # Koçaş (Koç Holding Araçları)
            "MNTAS",   # Mentas Hekim (varsa kontrol et)
            "OYAKC",   # Oyak Çimento
            "KRVTURB", # Karavelle Turizm (varsa kontrol et)
            "CCOLA",   # Coca-Cola
        ]
        
        # Duplikat hisseleri kaldır ve sırala
        symbols = sorted(list(set(symbols)))
        
        # Veri çekme parametreleri
        start_date = "2020-01-01"
        end_date = "2025-11-17"  # Bugünün tarihi
        output_dir = ROOT_DIR / "data" / "raw" / "ohlcv"
        
        logger.info(f"Toplam {len(symbols)} sembol için veri çekilecek")
        
        # İş Yatırım'dan veri çek
        fetch_ohlcv_from_isyatirim(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            output_dir=str(output_dir),
            rate_limit_delay=0.5,  # IP ban riski için bekleme
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
