import os
import requests
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def telegram_send(message: str):
    """Tek bir text mesajını Telegram'a gönderir."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        # "parse_mode": "Markdown"  # KALDIRDIK
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            print("Telegram hata:", resp.text)
        else:
            print("✅ Telegram'a mesaj gönderildi.")
    except Exception as e:
        print("Telegram gönderim hatası:", e)


if __name__ == "__main__":
    # Test için burası çalışacak
    telegram_send("🚀 Test mesajı: QuantTrade live sistemi aktif!")
