import os
import requests
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")


def telegram_send(message: str, use_backend: bool = True):
    """
    Telegram'a mesaj gönderir.
    
    Args:
        message: Gönderilecek mesaj
        use_backend: True ise backend API kullanılır, False ise direkt Telegram API
    """
    # Önce backend API ile göndermeyi dene
    if use_backend:
        try:
            backend_url = f"{BACKEND_API_URL}/api/telegram/broadcast"
            payload = {
                "message": message,
                "message_type": "INFO"
            }
            resp = requests.post(backend_url, json=payload, timeout=10)
            if resp.ok:
                result = resp.json()
                print(f"✅ Backend üzerinden mesaj gönderildi: {result.get('message', 'Success')}")
                return
            else:
                print(f"⚠️ Backend hatası ({resp.status_code}), direkt Telegram API'ye geçiliyor...")
        except Exception as e:
            print(f"⚠️ Backend'e erişilemiyor ({e}), direkt Telegram API'ye geçiliyor...")
    
    # Fallback: Direkt Telegram API kullan
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            print("Telegram hata:", resp.text)
        else:
            print("✅ Direkt Telegram API ile mesaj gönderildi.")
    except Exception as e:
        print("Telegram gönderim hatası:", e)


if __name__ == "__main__":
    # Test için burası çalışacak
    telegram_send("🚀 Test mesajı: QuantTrade live sistemi aktif!")
