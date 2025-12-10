"""
Telegram Bot Service - Manage Telegram bot and subscribers
Uses httpx for direct Telegram API calls (more reliable than python-telegram-bot for FastAPI)
"""
import json
import httpx
from pathlib import Path
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime
from config import settings
from models.schemas import (
    TelegramSubscriber, 
    TelegramSubscriberCreate,
    BroadcastMessage
)

# Telegram API Base URL
TELEGRAM_API_URL = "https://api.telegram.org"


class TelegramConfig(BaseModel):
    bot_token: Optional[str] = None  # Made optional
    bot_username: str = "@quant_alpha_bot"
    test_mode: bool = False  # Changed default to False for production use


class TelegramService:
    """Service for managing Telegram bot and subscribers"""
    
    def __init__(self):
        self.subscribers_path = settings.get_absolute_path(settings.subscribers_db_path)
        self.subscribers_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.bot_token: Optional[str] = settings.telegram_bot_token
        self.config = TelegramConfig(
            bot_token=settings.telegram_bot_token,
            bot_username=settings.telegram_bot_username,
            test_mode=False  # Default to production mode
        )
        
        # Validate bot token on init
        if self.bot_token:
            print(f"✅ Telegram Bot Token loaded (ends with ...{self.bot_token[-8:]})")
        else:
            print("⚠️ No Telegram Bot Token found in environment")
        
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
    
    async def _send_telegram_message(self, chat_id: str, text: str) -> Dict[str, any]:
        """Send message via Telegram API using httpx"""
        if not self.bot_token:
            return {"ok": False, "error": "No bot token configured"}
        
        url = f"{TELEGRAM_API_URL}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                result = response.json()
                
                if result.get("ok"):
                    return {"ok": True, "message_id": result.get("result", {}).get("message_id")}
                else:
                    error_desc = result.get("description", "Unknown error")
                    print(f"Telegram API error: {error_desc}")
                    return {"ok": False, "error": error_desc}
        except Exception as e:
            print(f"HTTP error sending to Telegram: {e}")
            return {"ok": False, "error": str(e)}
    
    async def send_message(self, chat_id: str, message: str) -> Dict[str, str]:
        """Send a message to a specific chat"""
        if not self.bot_token:
            return {"status": "error", "message": "Bot token not configured"}
        
        if self.config.test_mode:
            return {
                "status": "success",
                "message": f"[TEST MODE] Would send to {chat_id}: {message}"
            }
        
        result = await self._send_telegram_message(chat_id, message)
        
        if result.get("ok"):
            return {"status": "success", "message": "Message sent"}
        else:
            return {"status": "error", "message": result.get("error", "Unknown error")}
    
    async def broadcast_message(self, broadcast: BroadcastMessage) -> Dict[str, any]:
        """Broadcast a message to all active subscribers"""
        if not self.bot_token:
            return {
                "status": "error",
                "message": "Bot token not configured",
                "sent": 0,
                "failed": 0
            }
        
        # Format message
        message = self._format_broadcast_message(broadcast)
        
        # Get active subscribers
        active_subscribers = [sub for sub in self.subscribers if sub.active]
        
        if not active_subscribers:
            return {
                "status": "warning",
                "message": "No active subscribers to broadcast to",
                "sent": 0,
                "failed": 0
            }
        
        if self.config.test_mode:
            # Log message to history even in test mode
            self._log_message_to_history(broadcast)
            
            return {
                "status": "success",
                "message": f"[TEST MODE] Would broadcast to {len(active_subscribers)} subscribers",
                "sent": len(active_subscribers),
                "failed": 0
            }
        
        # Send to all active subscribers
        sent = 0
        failed = 0
        errors = []
        
        for sub in active_subscribers:
            result = await self._send_telegram_message(sub.chat_id, message)
            
            if result.get("ok"):
                sent += 1
                print(f"✅ Sent to {sub.name} ({sub.chat_id})")
            else:
                failed += 1
                error_msg = result.get("error", "Unknown error")
                errors.append(f"{sub.name}: {error_msg}")
                print(f"❌ Failed to send to {sub.name} ({sub.chat_id}): {error_msg}")
        
        # Log successful broadcast to history
        if sent > 0:
            self._log_message_to_history(broadcast)
        
        status_msg = f"Broadcast completed: {sent} sent, {failed} failed"
        if errors:
            status_msg += f"\nErrors: {'; '.join(errors[:3])}"  # Show first 3 errors
        
        return {
            "status": "success" if sent > 0 else "error",
            "message": status_msg,
            "sent": sent,
            "failed": failed
        }
    
    def _log_message_to_history(self, broadcast):
        """Log broadcast message to history file"""
        from datetime import datetime
        import json
        
        try:
            history = []
            history_path = settings.get_absolute_path("backend/data/message_history.json")
            history_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing history
            if history_path.exists():
                try:
                    with open(history_path, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except:
                    history = []
            
            # Handle both dict and BroadcastMessage
            if isinstance(broadcast, dict):
                message_entry = {
                    "id": len(history) + 1,
                    "type": broadcast.get("message_type", "INFO"),
                    "symbol": broadcast.get("symbol", "SYSTEM"),
                    "price": broadcast.get("price", 0),
                    "message": broadcast.get("message", ""),
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "SENT"
                }
            else:
                message_entry = {
                    "id": len(history) + 1,
                    "type": broadcast.message_type,
                    "symbol": broadcast.symbol or "SYSTEM",
                    "price": broadcast.price or 0,
                    "message": broadcast.message,
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "SENT"
                }
            
            history.append(message_entry)
            
            # Keep only last 100 messages
            history = history[-100:]
            
            # Save to file
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to log message history: {e}")
    
    def get_message_history(self, limit: int = 50) -> List[Dict]:
        """Get broadcast message history"""
        import json
        
        history_path = settings.get_absolute_path("backend/data/message_history.json")
        
        if not history_path.exists():
            return []
        
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            # Return most recent messages first
            return list(reversed(history[-limit:]))
        except Exception as e:
            print(f"Failed to load message history: {e}")
            return []
    
    def _format_broadcast_message(self, broadcast) -> str:
        """Format a broadcast message"""
        # Handle both dict and BroadcastMessage model
        if isinstance(broadcast, dict):
            message = broadcast.get('message', '')
            # For simple text broadcasts, return as-is
            return message
        
        # Original BroadcastMessage logic
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
