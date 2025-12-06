#!/usr/bin/env python3
"""
Portfolio V2 Daily Report Sender
Sends portfolio summary to Telegram via backend API
"""
import sys
import json
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

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
            print(f"✓ Sent to {result.get('sent', 0)} subscribers")
            return True
        else:
            print(f"✗ Error: {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def read_portfolio_state():
    """Read latest portfolio state"""
    state_path = project_root / "src/quanttrade/models_2.0/live_state_T1.json"
    
    if not state_path.exists():
        return None
    
    with open(state_path, 'r') as f:
        return json.load(f)


def format_portfolio_report(state):
    """Format portfolio as message"""
    cash = state.get('cash', 0)
    positions = state.get('positions', [])
    pending_buys = state.get('pending_buys', [])
    last_date = state.get('last_date', 'N/A')
    
    portfolio_value = sum(
        p.get('shares', 0) * p.get('current_price', p.get('entry_price', 0))
        for p in positions
    )
    total_equity = cash + portfolio_value
    
    message = f"""📊 Portfolio V2 Günlük Rapor

📅 Tarih: {last_date}
💰 Nakit: {cash:,.2f} TL
📈 Portföy: {portfolio_value:,.2f} TL
💼 Toplam: {total_equity:,.2f} TL

"""
    
    if positions:
        message += f"🔵 Aktif Pozisyonlar ({len(positions)}):\n"
        for p in positions:
            sym = p.get('symbol', '?')
            shares = p.get('shares', 0)
            entry = p.get('entry_price', 0)
            current = p.get('current_price', entry)
            pnl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0
            days = p.get('days_held', 0)
            
            status = ""
            if p.get('exit_planned'):
                status = f" [YARIN SAT: {p.get('exit_reason_planned', 'N/A')}]"
            
            message += f"  • {sym}: {shares} adet, {pnl_pct:+.1f}% ({days} gün){status}\n"
        message += "\n"
    else:
        message += "🔵 Aktif pozisyon yok\n\n"
    
    if pending_buys:
        message += f"🟢 Yarın Alım ({len(pending_buys)}):\n"
        for order in pending_buys:
            sym = order.get('symbol', '?')
            capital = order.get('planned_capital', 0)
            message += f"  • {sym}: ~{capital:,.0f} TL\n"
    else:
        message += "🟢 Yarın için alım yok\n"
    
    return message.strip()


def main():
    """Send portfolio report"""
    print("📤 Reading portfolio state...")
    
    state = read_portfolio_state()
    
    if not state:
        print("❌ Portfolio not found")
        return
    
    message = format_portfolio_report(state)
    
    print(f"📨 Broadcasting...")
    send_telegram_message(message)
    print(f"✅ Complete")


if __name__ == "__main__":
    main()
