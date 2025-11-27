#!/usr/bin/env python3
"""
Telegram Bot Main Entry Point
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from telegram_bot.bot_handler import start_bot

if __name__ == "__main__":
    print("🤖 Starting QuantTrade Telegram Bot...")
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
        sys.exit(1)
