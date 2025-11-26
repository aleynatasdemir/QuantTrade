# telegram_bot/daily_runner.py

import os
import sys
from dotenv import load_dotenv

# Proje kökünü sys.path'e ekle (live_engine ve telegram_bot'ı modül olarak görebilelim)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)  # ...\live-telegram
sys.path.append(ROOT_DIR)

# .env yükle (gerekirse)
load_dotenv()

from telegram_bot.telegram_notify import telegram_send
from live_engine import live_portfolio  # live_engine/live_portfolio.py


def run_and_notify():
    """
    live_portfolio.main() fonksiyonunu çalıştırır,
    dönen özet metni Telegram'a gönderir.
    """
    try:
        summary_text = live_portfolio.main()
    except Exception as e:
        err_msg = f"⚠️ Live script hata verdi:\n{e}"
        print(err_msg)
        telegram_send(err_msg)
        return

    if not summary_text:
        msg = "⚠️ Live script çalıştı ama summary döndürmedi."
        print(msg)
        telegram_send(msg)
        return

    # Telegram mesaj limiti için güvenlik payı
    if len(summary_text) > 3800:
        summary_text = summary_text[-3800:]

    print("===== TELEGRAM'A GÖNDERİLEN METİN =====")
    print(summary_text)
    print("========================================")

    telegram_send(summary_text)


if __name__ == "__main__":
    run_and_notify()
