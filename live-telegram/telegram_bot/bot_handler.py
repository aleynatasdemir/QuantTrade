"""
Telegram Bot Command Handler
Handles /start, /subscribe, /unsubscribe, /status, /trade commands
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Docker'da backend service adı "backend", local'de localhost
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend:8000")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show chat ID"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    message = f"""
🤖 **QuantTrade Bot**

Hoş geldiniz {user.first_name}!

📋 **Bilgileriniz:**
• Chat ID: `{chat_id}`
• Kullanıcı Adı: @{user.username or 'N/A'}
• İsim: {user.first_name} {user.last_name or ''}

📌 **Abone olmak için:**
Admin'e şu bilgileri iletin ya da `/subscribe` komutunu kullanın.

💡 **Komutlar:**
/start - Bu mesajı göster
/subscribe - Otomatik abone ol
/unsubscribe - Aboneliği iptal et
/status - Abone durumunu göster
/trade - Portfolio analizi çalıştır (Admin)
/gpt - Son GPT analizi göster
    """
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - Auto subscribe user"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Try to add subscriber via backend API
    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/telegram/subscribers",
            json={
                "name": f"{user.first_name} {user.last_name or ''}".strip(),
                "chat_id": str(chat_id),
                "role": "Trader"
            },
            timeout=10
        )
        
        if response.ok:
            await update.message.reply_text(
                "✅ Başarıyla abone oldunuz!\n\n"
                "Artık günlük trading sinyallerini alacaksınız. 📈"
            )
        else:
            await update.message.reply_text(
                "⚠️ Abone olurken bir hata oluştu.\n\n"
                f"Lütfen admin ile iletişime geçin.\nChat ID: `{chat_id}`",
                parse_mode='Markdown'
            )
    except Exception as e:
        print(f"Error subscribing user: {e}")
        await update.message.reply_text(
            "❌ Backend'e bağlanılamadı.\n\n"
            f"Manuel eklemek için Chat ID: `{chat_id}`",
            parse_mode='Markdown'
        )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command - Deactivate subscription"""
    chat_id = update.effective_chat.id
    
    try:
        # Get all subscribers
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/subscribers",
            timeout=10
        )
        
        if response.ok:
            subscribers = response.json()
            user_sub = next((s for s in subscribers if s['chat_id'] == str(chat_id)), None)
            
            if user_sub:
                # Deactivate user
                update_response = requests.put(
                    f"{BACKEND_API_URL}/api/telegram/subscribers/{user_sub['id']}",
                    json={"active": False},
                    timeout=10
                )
                
                if update_response.ok:
                    await update.message.reply_text(
                        "✅ Aboneliğiniz iptal edildi.\n\n"
                        "Tekrar abone olmak için /subscribe kullanın."
                    )
                else:
                    await update.message.reply_text("⚠️ Abonelik iptal edilemedi.")
            else:
                await update.message.reply_text(
                    "ℹ️ Zaten abone değilsiniz.\n\n"
                    "Abone olmak için /subscribe kullanın."
                )
        else:
            await update.message.reply_text("⚠️ Sunucuya bağlanılamadı.")
            
    except Exception as e:
        print(f"Error unsubscribing user: {e}")
        await update.message.reply_text("❌ Bir hata oluştu.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - Show subscription status"""
    chat_id = update.effective_chat.id
    
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/subscribers",
            timeout=10
        )
        
        if response.ok:
            subscribers = response.json()
            user_sub = next((s for s in subscribers if s['chat_id'] == str(chat_id)), None)
            
            if user_sub:
                status_emoji = "✅" if user_sub['active'] else "⏸"
                status_text = "Aktif" if user_sub['active'] else "Pasif"
                
                message = f"""
📊 **Abonelik Durumunuz**

{status_emoji} Durum: **{status_text}**
👤 İsim: {user_sub['name']}
🏷 Rol: {user_sub['role']}
💬 Chat ID: `{chat_id}`
                """
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    "ℹ️ Abone değilsiniz.\n\n"
                    f"Chat ID: `{chat_id}`\n"
                    "Abone olmak için /subscribe kullanın.",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text("⚠️ Durum sorgulanamadı.")
            
    except Exception as e:
        print(f"Error checking status: {e}")
        await update.message.reply_text("❌ Bir hata oluştu.")


async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Broadcasts a message to all active subscribers."""
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/telegram/subscribers", timeout=10)
        if response.ok:
            subscribers = response.json()
            for sub in subscribers:
                if sub.get("active"):
                    try:
                        await context.bot.send_message(chat_id=sub["chat_id"], text=message, parse_mode='Markdown')
                    except Exception as e:
                        print(f"Error sending message to {sub['chat_id']}: {e}")
        else:
            print(f"Error fetching subscribers for broadcast: {response.status_code}")
    except Exception as e:
        print(f"Error in broadcast_message: {e}")


async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trade - Show latest portfolio analysis (Admin only)
    Reads cached summary from live_summary_telegram.json
    """
    chat_id = update.effective_chat.id
    
    # Get subscriber info
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/telegram/subscribers", timeout=10)
        if not response.ok:
            await update.message.reply_text("❌ Subscriber bilgisi alınamadı")
            return
        
        subscribers = response.json()
        user_sub = next((s for s in subscribers if s["chat_id"] == str(chat_id)), None)
        
        if not user_sub or user_sub.get("role") != "Admin":
            await update.message.reply_text("❌ Bu komutu sadece Admin kullanabilir")
            return
    except Exception as e:
        print(f"Error checking permissions: {e}")
        await update.message.reply_text(f"❌ Yetki kontrolünde hata: {e}")
        return
    
    # Try to read cached summary
    try:
        # Possible paths for the summary file
        possible_paths = [
            Path("/app/src/quanttrade/models_2.0/live_summary_telegram.json"),  # Docker
            Path(__file__).parent.parent.parent / "src" / "quanttrade" / "models_2.0" / "live_summary_telegram.json",  # Local
        ]
        
        summary_data = None
        for summary_path in possible_paths:
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                break
        
        if summary_data:
            message = summary_data.get("message", "Özet bulunamadı")
            timestamp = summary_data.get("timestamp", "N/A")
            
            # Send the cached summary
            await update.message.reply_text(message, parse_mode='Markdown')
            
            # Broadcast to all active subscribers
            await broadcast_message(context, message)
        else:
            await update.message.reply_text(
                "❌ Günlük portfolio özeti bulunamadı.\n\n"
                "Portfolio script henüz bugün çalışmamış olabilir.\n"
                "Script her gün borsa kapandıktan sonra otomatik çalışır."
            )
            
    except json.JSONDecodeError as e:
        await update.message.reply_text(f"❌ Özet dosyası bozuk: {e}")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Trade command error: {error_details}")
        await update.message.reply_text(f"❌ Hata: {str(e)}")


async def gpt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /gpt command - Show latest GPT analysis"""
    chat_id = update.effective_chat.id
    
    try:
        # Try to read GPT analysis from file (like trade_command)
        possible_paths = [
            Path("/app/src/quanttrade/models_2.0/gpt_analysis_latest.json"),  # Docker
            Path(__file__).parent.parent.parent / "src" / "quanttrade" / "models_2.0" / "gpt_analysis_latest.json",  # Local
        ]
        
        gpt_data = None
        for gpt_path in possible_paths:
            if gpt_path.exists():
                with open(gpt_path, 'r', encoding='utf-8') as f:
                    gpt_data = json.load(f)
                break
        
        if not gpt_data:
            await update.message.reply_text(
                "❌ GPT analiz dosyası bulunamadı.\n\n"
                "GPT analizi henüz çalışmamış olabilir."
            )
            return
        
        timestamp = gpt_data.get("timestamp", "N/A")
        as_of_date = gpt_data.get("as_of_date", "N/A")
        analysis_text = gpt_data.get("analysis", "")
        
        # Clean markdown code blocks if present
        if analysis_text.startswith("```"):
            analysis_text = analysis_text.strip("`").strip()
            if analysis_text.startswith("\n"):
                analysis_text = analysis_text[1:]
        
        # Parse timestamp for display
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%d.%m.%Y %H:%M")
        except:
            time_str = timestamp
        
        # Telegram message limit is 4096 characters
        MAX_LENGTH = 4000  # Leave some margin
        
        # Header message
        header = f"""🤖 GPT Portfolio Analizi

📅 Tarih: {as_of_date}
🕒 Analiz: {time_str}
"""
        
        # Send header first
        await update.message.reply_text(header)
        
        # Split analysis text into chunks if needed
        if len(analysis_text) > MAX_LENGTH:
            # Split into chunks
            chunks = []
            current_chunk = ""
            
            for line in analysis_text.split('\n'):
                if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += ('\n' if current_chunk else '') + line
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send each chunk
            for i, chunk in enumerate(chunks, 1):
                part_msg = f"📄 Bölüm {i}/{len(chunks)}\n\n{chunk}"
                await update.message.reply_text(part_msg)
        else:
            # Single message
            await update.message.reply_text(analysis_text)
            
    except json.JSONDecodeError as e:
        await update.message.reply_text(f"❌ GPT analiz dosyası bozuk: {e}")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"GPT command error: {error_details}")
        await update.message.reply_text(f"❌ Hata: {str(e)}")


def main():
    """Start the bot"""
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN bulunamadı!")
        return
    
    print("🤖 QuantTrade Bot başlatılıyor...")
    print(f"📡 Backend: {BACKEND_API_URL}")
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("trade", trade_command))
    application.add_handler(CommandHandler("gpt", gpt_command))
    
    print("✅ Bot hazır! Komutlar dinleniyor...")
    print("\n💡 Kullanılabilir komutlar:")
    print("   /start - Bot bilgisi ve Chat ID")
    print("   /subscribe - Otomatik abone ol")
    print("   /unsubscribe - Aboneliği iptal et")
    print("   /status - Abone durumu")
    print("   /trade - Portfolio analizi çalıştır (Admin)")
    print("   /gpt - Son GPT analizi göster")
    print("\n🔄 Bot çalışıyor... (Durdurmak için Ctrl+C)")
    
    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def start_bot():
    """Async entry point for Docker/main.py"""
    main()


if __name__ == "__main__":
    main()
