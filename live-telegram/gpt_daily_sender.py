#!/usr/bin/env python3
"""
GPT Daily Telegram Sender
Reads latest GPT analysis and broadcasts to all Telegram subscribers
Run via cron at 09:50
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.gpt_service import get_latest_analysis, format_for_telegram
from backend.services.telegram_service import telegram_service


def main():
    """Send latest GPT analysis to all subscribers"""
    print("📤 Reading latest GPT analysis...")
    
    analysis = get_latest_analysis()
    
    if not analysis:
        print("❌ No GPT analysis found. Skipping broadcast.")
        return
    
    # Format without Markdown
    timestamp = analysis.get('timestamp', 'N/A')
    as_of_date = analysis.get('as_of_date', 'N/A')
    text = analysis.get('analysis', '')
    
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%d.%m.%Y %H:%M")
    except:
        time_str = timestamp
    
    # Telegram message limit is 4096 characters
    MAX_LENGTH = 4000
    
    # Send header first
    header = f"""🤖 GPT Portfolio Analizi

📅 Tarih: {as_of_date}
🕒 Analiz: {time_str}
"""
    
    print(f"📨 Broadcasting GPT analysis to subscribers...")
    print(f"   Timestamp: {timestamp}")
    print(f"   As of: {as_of_date}")
    print(f"   Analysis length: {len(text)} chars")
    
    # Broadcast header
    telegram_service.broadcast_message({"message": header})
    
    # Split and send analysis text if needed
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
            telegram_service.broadcast_message({"message": part_msg})
    else:
        print(f"❌ Broadcast failed: {result.get('error')}")


if __name__ == "__main__":
    main()
