"""
Standalone Telegram Bot for QuantTrade
Monitors portfolio state and sends daily signals to subscribers
"""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SUBSCRIBERS_DB = Path("backend/data/subscribers.json")
LIVE_STATE_PATH = Path("src/quanttrade/models_2.0/live_state_T1.json")
LAST_NOTIFICATION_FILE = Path("backend/data/last_notification.json")

# Ensure data directory exists
SUBSCRIBERS_DB.parent.mkdir(parents=True, exist_ok=True)


class TelegramBot:
    """Telegram bot for QuantTrade signals"""
    
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.subscribers: List[Dict] = []
        self.last_state = None
        
        # Load subscribers
        self._load_subscribers()
        
        # Register handlers
        self._register_handlers()
    
    def _load_subscribers(self):
        """Load subscribers from JSON file"""
        if SUBSCRIBERS_DB.exists():
            try:
                with open(SUBSCRIBERS_DB, 'r', encoding='utf-8') as f:
                    self.subscribers = json.load(f)
                logger.info(f"Loaded {len(self.subscribers)} subscribers")
            except Exception as e:
                logger.error(f"Failed to load subscribers: {e}")
                self.subscribers = []
        else:
            self.subscribers = []
    
    def _save_subscribers(self):
        """Save subscribers to JSON file"""
        try:
            with open(SUBSCRIBERS_DB, 'w', encoding='utf-8') as f:
                json.dump(self.subscribers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save subscribers: {e}")
    
    def _register_handlers(self):
        """Register command handlers"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        self.application.add_handler(CommandHandler("unsubscribe", self.cmd_unsubscribe))
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = (
            "🤖 *QuantTrade Bot*\\n\\n"
            "Hoş geldiniz\\! Bu bot günlük alım\\-satım sinyalleri gönderir\\.\\n\\n"
            "*Komutlar:*\\n"
            "/subscribe \\- Sinyal bildirimlerine abone ol\\n"
            "/unsubscribe \\- Abonelikten çık\\n"
            "/status \\- Portföy durumunu görüntüle\\n"
            "/help \\- Yardım mesajı"
        )
        await update.message.reply_text(welcome_message, parse_mode='MarkdownV2')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = (
            "📚 *Yardım*\\n\\n"
            "*Komutlar:*\\n"
            "/start \\- Botu başlat\\n"
            "/subscribe \\- Günlük sinyallere abone ol\\n"
            "/unsubscribe \\- Abonelikten çık\\n"
            "/status \\- Mevcut portföy durumu\\n\\n"
            "*Hakkında:*\\n"
            "Bu bot QuantTrade algoritması tarafından üretilen "
            "alım\\-satım sinyallerini otomatik olarak gönderir\\."
        )
        await update.message.reply_text(help_message, parse_mode='MarkdownV2')
    
    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe command"""
        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "User"
        
        # Check if already subscribed
        if any(sub['chat_id'] == chat_id for sub in self.subscribers):
            await update.message.reply_text("✅ Zaten abone durumdasınız!")
            return
        
        # Add new subscriber
        new_subscriber = {
            "id": len(self.subscribers) + 1,
            "name": user_name,
            "chat_id": chat_id,
            "role": "Trader",
            "active": True,
            "avatar_color": "bg-cyan-600"
        }
        
        self.subscribers.append(new_subscriber)
        self._save_subscribers()
        
        await update.message.reply_text(
            f"✅ Başarıyla abone oldunuz!\n\n"
            f"Günlük alım-satım sinyalleri bu sohbete gönderilecek."
        )
        logger.info(f"New subscriber: {user_name} ({chat_id})")
    
    async def cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unsubscribe command"""
        chat_id = str(update.effective_chat.id)
        
        # Remove subscriber
        original_count = len(self.subscribers)
        self.subscribers = [sub for sub in self.subscribers if sub['chat_id'] != chat_id]
        
        if len(self.subscribers) < original_count:
            self._save_subscribers()
            await update.message.reply_text("✅ Abonelikten çıktınız.")
            logger.info(f"Unsubscribed: {chat_id}")
        else:
            await update.message.reply_text("❌ Abone değilsiniz.")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            if not LIVE_STATE_PATH.exists():
                await update.message.reply_text("⚠️ Portföy verisi bulunamadı.")
                return
            
            with open(LIVE_STATE_PATH, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Format status message
            cash = state.get('cash', 0)
            positions = state.get('positions', [])
            pending_buys = state.get('pending_buys', [])
            last_date = state.get('last_date', 'N/A')
            
            message = (
                f"📊 *Portföy Durumu*\n\n"
                f"💰 Nakit: ₺{cash:,.2f}\n"
                f"📈 Aktif Pozisyon: {len(positions)}\n"
                f"⏳ Bekleyen Emir: {len(pending_buys)}\n"
                f"📅 Son Güncelleme: {last_date}\n\n"
            )
            
            if pending_buys:
                message += "*Bekleyen Alımlar:*\n"
                for buy in pending_buys[:5]:  # Show max 5
                    symbol = buy.get('symbol', 'N/A')
                    capital = buy.get('planned_capital', 0)
                    message += f"• {symbol}: ₺{capital:,.0f}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("❌ Durum bilgisi alınamadı.")
    
    async def send_daily_signals(self):
        """Send daily signals to all active subscribers"""
        try:
            if not LIVE_STATE_PATH.exists():
                logger.warning("Live state file not found")
                return
            
            with open(LIVE_STATE_PATH, 'r', encoding='utf-8') as f:
                current_state = json.load(f)
            
            # Check if state has changed
            if self._has_state_changed(current_state):
                await self._broadcast_signals(current_state)
                self.last_state = current_state
                self._save_last_notification(current_state)
        
        except Exception as e:
            logger.error(f"Error sending daily signals: {e}")
    
    def _has_state_changed(self, current_state: Dict) -> bool:
        """Check if portfolio state has changed"""
        if self.last_state is None:
            # Load last notification state
            if LAST_NOTIFICATION_FILE.exists():
                try:
                    with open(LAST_NOTIFICATION_FILE, 'r') as f:
                        self.last_state = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading last notification: {e}")
                    return True
            else:
                return True
        
        # Compare pending buys
        last_pending = set(b['symbol'] for b in self.last_state.get('pending_buys', []))
        current_pending = set(b['symbol'] for b in current_state.get('pending_buys', []))
        
        return last_pending != current_pending
    
    def _save_last_notification(self, state: Dict):
        """Save last notification state"""
        try:
            with open(LAST_NOTIFICATION_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving last notification: {e}")
    
    async def _broadcast_signals(self, state: Dict):
        """Broadcast signals to all active subscribers"""
        pending_buys = state.get('pending_buys', [])
        
        if not pending_buys:
            return
        
        # Format message
        message = (
            f"📈 *Yeni Alım Sinyalleri*\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        )
        
        for buy in pending_buys:
            symbol = buy.get('symbol', 'N/A')
            capital = buy.get('planned_capital', 0)
            message += f"🔹 *{symbol}*: ₺{capital:,.0f}\n"
        
        message += (
            f"\n💡 Bu sinyaller yarın sabah açılışta işleme alınacak.\n"
            f"⚠️ Risk yönetimine dikkat edin!"
        )
        
        # Send to all active subscribers
        active_subscribers = [sub for sub in self.subscribers if sub.get('active', True)]
        
        for sub in active_subscribers:
            try:
                await self.application.bot.send_message(
                    chat_id=sub['chat_id'],
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Signal sent to {sub['name']} ({sub['chat_id']})")
            except Exception as e:
                logger.error(f"Failed to send to {sub['chat_id']}: {e}")
    
    async def monitor_portfolio(self):
        """Monitor portfolio state and send signals when changed"""
        logger.info("Starting portfolio monitoring...")
        
        while True:
            try:
                await self.send_daily_signals()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Check every 5 minutes
            await asyncio.sleep(300)
    
    def run(self):
        """Run the bot"""
        logger.info("Starting QuantTrade Telegram Bot...")
        
        # Start monitoring in background
        self.application.job_queue.run_repeating(
            lambda context: asyncio.create_task(self.send_daily_signals()),
            interval=300,  # 5 minutes
            first=10  # Start after 10 seconds
        )
        
        # Start the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point"""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment variables!")
        return
    
    bot = TelegramBot(BOT_TOKEN)
    bot.run()


if __name__ == "__main__":
    main()
