#!/usr/bin/env python3
"""
GPT Daily Report Sender
Sends latest GPT analysis to Telegram subscribers via backend API
"""
import sys
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

from backend.services.gpt_service import get_latest_analysis

BACKEND_API_URL = "http://localhost:8000"


def send_telegram_message(message: str):
    """Send message via backend API"""
    try:
        url = f"{BACKEND_API_URL}/api/telegram/broadcast"
        payload = {
            "message": message,
            "message_type": "INFO"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            result = resp.json()
            print(f"✓ Sent: {result.get('sent', 0)} subscribers")
            return True
        else:
            print(f"✗ Backend error: {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Send latest GPT analysis to all subscribers"""
    print("📤 Reading latest GPT analysis...")
    
    analysis = get_latest_analysis()
    
    if not analysis:
        print("❌ No GPT analysis found. Skipping broadcast.")
        return
    
    timestamp = analysis.get('timestamp', 'N/A')
    as_of_date = analysis.get('as_of_date', 'N/A')
    text = analysis.get('analysis', '')
    
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%d.%m.%Y %H:%M")
    except:
        time_str = timestamp
    
    # Telegram message limit
    MAX_LENGTH = 4000
    
    # Send header first
    header = f"""🤖 GPT Portfolio Analizi

📅 Tarih: {as_of_date}
🕒 Analiz: {time_str}
"""
    
    print(f"📨 Broadcasting to subscribers...")
    send_telegram_message(header)
    
    # Split and send if needed
    if len(text) > MAX_LENGTH:
        chunks = []
        current_chunk = ""
        
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += ('\n' if current_chunk else '') + line
        
        if current_chunk:
            chunks.append(current_chunk)
        
        print(f"   Splitting into {len(chunks)} parts...")
        
        for i, chunk in enumerate(chunks, 1):
            part_msg = f"📄 Bölüm {i}/{len(chunks)}\n\n{chunk}"
            send_telegram_message(part_msg)
    else:
        send_telegram_message(text)
    
    print(f"✅ Broadcast complete")


if __name__ == "__main__":
    main()
