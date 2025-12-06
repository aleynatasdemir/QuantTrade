"""
Simple test script to verify Telegram notification works
"""
import sys
import os

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot.telegram_notify import telegram_send

# Send test message
message = """
🚀 QuantTrade Test Message

✅ Telegram notification system is working!
📊 Backend API integration: Active
🤖 Bot handler: Running

This is a test message from live-telegram.
"""

print("Sending test message to Telegram...")
telegram_send(message)
print("Done!")
