import os
import pandas as pd
import numpy as np


CATEGORY_MAPPING = {
    # GENEL_BILGI
    "GENEL_BILGI": "GENEL_BILGI",
    "ROUTINE_BILGI": "GENEL_BILGI",
    "ROUTINE_BILGILER": "GENEL_BILGI",
    "ROUTINE_INFO": "GENEL_BILGI",
    "rutin_bilgilendirme": "GENEL_BILGI",
    "rutin_bilgilendirmesi": "GENEL_BILGI",
    "TEDBIR": "GENEL_BILGI",
    "TEDBIR_UYGULANMASI": "GENEL_BILGI",
    "ORGANIZASYONEL_DEGISIKLIK": "GENEL_BILGI",
    "YETKILILIK": "GENEL_BILGI",
    "YETKILILIK_KARAR": "GENEL_BILGI",
    "YETKILİDEN_BILGI": "GENEL_BILGI",
    "YETKILİMESLEMI": "GENEL_BILGI",
    "YETKILİMESLİK": "GENEL_BILGI",
    "YETKILİ_BİLGİ": "GENEL_BILGI",
    "YETKILİ_DEFTERLEME": "GENEL_BILGI",
    "YETKILİ_KAYIT": "GENEL_BILGI",
    "YETKILİ_KURUL_KARAR": "GENEL_BILGI",
    "YETKILİ_KURUL_RAPORU": "GENEL_BILGI",
    "YETkilendirmesi": "GENEL_BILGI",
    "PARSE_ERROR": "GENEL_BILGI",
    "FAALIYETLERIN_KISMEN_VYA_TAMAMEN_DURDURULMASI_YA_DA_IMKANSIZ_HALE_GELMESI": "GENEL_BILGI",
    "KAYIP_AYDINLATMA": "GENEL_BILGI",
    "ZORUNLU_PAY_ALIM": "GENEL_BILGI",

    # FINANSAL_RAPOR
    "FINANSAL_RAPOR": "FINANSAL_RAPOR",
    "KAR_ARTISI": "FINANSAL_RAPOR",
    "Kâr_Artışı": "FINANSAL_RAPOR",
    "Kâr_artışı": "FINANSAL_RAPOR",
    "KREDI_DERECELENDIRME": "FINANSAL_RAPOR",
    "KREDİ_DERECELENDİRME": "FINANSAL_RAPOR",
    "Kredi_Derecelendirme": "FINANSAL_RAPOR",
    "Kredi_Derecelendirmesi": "FINANSAL_RAPOR",
    "DÖVİZ_KARARLI_SEMVER": "FINANSAL_RAPOR",
    "MADDI_DURAN_VARLIK_SATIMI": "FINANSAL_RAPOR",
    "MADDI_DURAN_VARLIK_SATISI": "FINANSAL_RAPOR",
    "NAKDI_UZLASIH_ODEMELERI": "FINANSAL_RAPOR",
    "Nakit_Uzlasici_Odeme": "FINANSAL_RAPOR",
    "Nakit_Uzlasimi_Odeme": "FINANSAL_RAPOR",
    "Nakit_Uzlasma_Odeme": "FINANSAL_RAPOR",
    "TOPTAN_ALIS_SATIS": "FINANSAL_RAPOR",

    # YATIRIM_SOZLESME
    "YATIRIM_SOZLESME": "YATIRIM_SOZLESME",
    "YENILENECEK_ENERJI": "YATIRIM_SOZLESME",
    "YENİ_YATIRIM": "YATIRIM_SOZLESME",
    "YENİ_YATIRIM_SÖZLEŞMESI": "YATIRIM_SOZLESME",
    "YETIRIM/YATIRIM": "YATIRIM_SOZLESME",
    "YETIRIM_KAYNAKLI_KONU": "YATIRIM_SOZLESME",

    # SERMAYE_TEMETTU
    "SERMAYE_TEMETTU": "SERMAYE_TEMETTU",
    "TEMETTU": "SERMAYE_TEMETTU",
    "KAR_DAĞITIMI": "SERMAYE_TEMETTU",
    "KAR_PAYI_DAĞITIM": "SERMAYE_TEMETTU",
    "KAR_PAYI_DAĞITIMI": "SERMAYE_TEMETTU",
    "KAR_PAYI_AVANSI": "SERMAYE_TEMETTU",
    "KAR_AVANSI": "SERMAYE_TEMETTU",
    "KAYITLI_KAR_DAĞITIMI": "SERMAYE_TEMETTU",
    "KAYITLI_PAY": "SERMAYE_TEMETTU",
    "KAYNAK_KAR": "SERMAYE_TEMETTU",
    "KAYNAK_KARLIKLARI": "SERMAYE_TEMETTU",
    "SERMAYE_PIYASASI_ARACI_ISLEMLERI": "SERMAYE_TEMETTU",

    # ILISKILI_TARAF
    "ILISKILI_TARAF_ISLEMLERI": "ILISKILI_TARAF",
}


def normalize_category(cat: str) -> str:
    if pd.isna(cat) or cat == "":
        return "GENEL_BILGI"

    c = str(cat).strip()
    if c in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[c]

    cu = c.upper()

    if "YATIRIM" in cu or "SÖZLEŞ" in cu or "INVEST" in cu:
        return "YATIRIM_SOZLESME"

    if "TEMET" in cu or "KAR_PAYI" in cu or "SERMAYE" in cu:
        return "SERMAYE_TEMETTU"

    if "KRED" in cu or "FINANS" in cu or "RAPOR" in cu:
        return "FINANSAL_RAPOR"

    if "İLİŞKİLİ" in cu or "ILISKILI" in cu:
        return "ILISKILI_TARAF"

    return "GENEL_BILGI"


def clean_kap_predictions(input_dir: str, output_dir: str = None, verbose: bool = True):

    if output_dir is None:
        base_dir = os.path.dirname(os.path.dirname(input_dir))
        output_dir = os.path.join(base_dir, "processed", "kap")
    os.makedirs(output_dir, exist_ok=True)

    print(f"[INFO] input_dir: {input_dir}")
    print(f"[INFO] output_dir: {output_dir}")
    print(f"[INFO] files in input_dir: {os.listdir(input_dir)}")

    for filename in sorted(os.listdir(input_dir)):

        # --- TÜM CSV DOSYALARINI AL ---
        if not filename.endswith(".csv"):
            continue

        path = os.path.join(input_dir, filename)
        symbol = filename.replace(".csv", "")

        print(f"[DEBUG] processing: {filename}")

        df = pd.read_csv(path)

        # sentiment ve volatility tamamen dokunulmadan bırakılır
        df["sentiment"] = df["sentiment"].fillna(0)
        df["volatility"] = df["volatility"].fillna(0).astype(int)

        # kategori normalize edilir
        df["category"] = df["category"].apply(normalize_category)

        # symbol kolonunu garanti altına al
        if "symbol" not in df.columns:
            df["symbol"] = symbol

        # tarih formatını düzelt
        if "tarih" in df.columns:
            df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce")
            df = df.dropna(subset=["tarih"])
            df["tarih"] = df["tarih"].dt.strftime("%Y-%m-%d")


        # çıktı: sadece kendi dosyasına kaydedilir (merge YOK)
        output_path = os.path.join(output_dir, filename)
        df.to_csv(output_path, index=False)

        print(f"✓ {filename}: {len(df)} satır temizlendi")

    print("\n[INFO] Tüm CSV dosyaları işlendi.")


if __name__ == "__main__":
    import pathlib
    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
    input_dir = ROOT / "data" / "raw" / "kap"
    clean_kap_predictions(str(input_dir))
