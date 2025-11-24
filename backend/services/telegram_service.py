"""
Telegram Bot Service - Manage Telegram bot and subscribers
"""
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from backend.config import settings
from backend.models.schemas import (
    TelegramConfig, 
    TelegramSubscriber, 
    TelegramSubscriberCreate,
    BroadcastMessage
)


class TelegramService:
    """Service for managing Telegram bot and subscribers"""
    
    def __init__(self):
        self.subscribers_path = settings.get_absolute_path(settings.subscribers_db_path)
        self.subscribers_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.bot: Optional[Bot] = None
        self.config = TelegramConfig(
            bot_token=settings.telegram_bot_token,
            bot_username=settings.telegram_bot_username,
            test_mode=True
        )
        
        # Initialize bot if token is available
        if settings.telegram_bot_token:
            try:
                self.bot = Bot(token=settings.telegram_bot_token)
            except Exception as e:
                print(f"Failed to initialize Telegram bot: {e}")
        
        # Load subscribers
        self._load_subscribers()
    
    def _load_subscribers(self):
        """Load subscribers from JSON file"""
        if self.subscribers_path.exists():
            try:
                with open(self.subscribers_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.subscribers = [TelegramSubscriber(**sub) for sub in data]
            except Exception as e:
                print(f"Failed to load subscribers: {e}")
                self.subscribers = []
        else:
            self.subscribers = []
    
    def _save_subscribers(self):
        """Save subscribers to JSON file"""
        try:
            with open(self.subscribers_path, 'w', encoding='utf-8') as f:
                data = [sub.model_dump() for sub in self.subscribers]
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save subscribers: {e}")
    
    def get_config(self) -> TelegramConfig:
        """Get current bot configuration"""
        return self.config
    
    def update_config(self, bot_token: Optional[str] = None, 
                     bot_username: Optional[str] = None,
                     test_mode: Optional[bool] = None) -> TelegramConfig:
        """Update bot configuration"""
        if bot_token is not None:
            self.config.bot_token = bot_token
            # Reinitialize bot with new token
            try:
                self.bot = Bot(token=bot_token)
            except Exception as e:
                raise ValueError(f"Invalid bot token: {e}")
        
        if bot_username is not None:
            self.config.bot_username = bot_username
        
        if test_mode is not None:
            self.config.test_mode = test_mode
        
        return self.config
    
    def get_subscribers(self) -> List[TelegramSubscriber]:
        """Get all subscribers"""
        return self.subscribers
    
    def add_subscriber(self, subscriber_data: TelegramSubscriberCreate) -> TelegramSubscriber:
        """Add a new subscriber"""
        # Generate new ID
        new_id = max([sub.id for sub in self.subscribers], default=0) + 1
        
        new_subscriber = TelegramSubscriber(
            id=new_id,
            name=subscriber_data.name,
            chat_id=subscriber_data.chat_id,
            role=subscriber_data.role,
            active=True,
            avatar_color="bg-cyan-600"
        )
        
        self.subscribers.append(new_subscriber)
        self._save_subscribers()
        
        return new_subscriber
    
    def update_subscriber(self, subscriber_id: int, 
                         name: Optional[str] = None,
                         active: Optional[bool] = None,
                         role: Optional[str] = None) -> Optional[TelegramSubscriber]:
        """Update a subscriber"""
        for sub in self.subscribers:
            if sub.id == subscriber_id:
                if name is not None:
                    sub.name = name
                if active is not None:
                    sub.active = active
                if role is not None:
                    sub.role = role
                
                self._save_subscribers()
                return sub
        
        return None
    
    def delete_subscriber(self, subscriber_id: int) -> bool:
        """Delete a subscriber"""
        original_count = len(self.subscribers)
        self.subscribers = [sub for sub in self.subscribers if sub.id != subscriber_id]
        
        if len(self.subscribers) < original_count:
            self._save_subscribers()
            return True
        
        return False
    
    async def send_message(self, chat_id: str, message: str) -> Dict[str, str]:
        """Send a message to a specific chat"""
        if not self.bot:
            return {"status": "error", "message": "Bot not initialized"}
        
        if self.config.test_mode:
            return {
                "status": "success",
                "message": f"[TEST MODE] Would send to {chat_id}: {message}"
            }
        
        try:
            await self.bot.send_message(chat_id=chat_id, text=message)
            return {"status": "success", "message": "Message sent"}
        except TelegramError as e:
            return {"status": "error", "message": str(e)}
    
    async def broadcast_message(self, broadcast: BroadcastMessage) -> Dict[str, any]:
        """Broadcast a message to all active subscribers"""
        if not self.bot:
            return {
                "status": "error",
                "message": "Bot not initialized",
                "sent": 0,
                "failed": 0
            }
        
        # Format message
        message = self._format_broadcast_message(broadcast)
        
        # Get active subscribers
        active_subscribers = [sub for sub in self.subscribers if sub.active]
        
        if self.config.test_mode:
            return {
                "status": "success",
                "message": f"[TEST MODE] Would broadcast to {len(active_subscribers)} subscribers",
                "sent": len(active_subscribers),
                "failed": 0
            }
        
        # Send to all active subscribers
        sent = 0
        failed = 0
        
        for sub in active_subscribers:
            try:
                await self.bot.send_message(chat_id=sub.chat_id, text=message)
                sent += 1
            except TelegramError as e:
                print(f"Failed to send to {sub.name} ({sub.chat_id}): {e}")
                failed += 1
        
        return {
            "status": "success",
            "message": f"Broadcast completed: {sent} sent, {failed} failed",
            "sent": sent,
            "failed": failed
        }
    
    def _format_broadcast_message(self, broadcast: BroadcastMessage) -> str:
        """Format a broadcast message"""
        icon = "📈" if broadcast.message_type == "BUY" else "📉" if broadcast.message_type == "SELL" else "ℹ️"
        
        if broadcast.symbol and broadcast.price:
            header = f"{icon} {broadcast.message_type} {broadcast.symbol}\n₺{broadcast.price:.2f}\n\n"
        elif broadcast.symbol:
            header = f"{icon} {broadcast.message_type} {broadcast.symbol}\n\n"
        else:
            header = f"{icon} {broadcast.message_type}\n\n"
        
        return header + broadcast.message


# Global service instance
telegram_service = TelegramService()
