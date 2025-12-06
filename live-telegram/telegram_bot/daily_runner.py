#!/usr/bin/env python3
"""
Daily runner for live portfolio - runs live_portfolio_manager.py and sends output to Telegram
"""
import os
import sys
import subprocess
from pathlib import Path
from telegram_notify import telegram_send

def main():
    """Run live portfolio manager and send results to Telegram"""
    
    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    portfolio_script = project_root / "src" / "quanttrade" / "models_2.0" / "live_portfolio_v2.py"
    
    if not portfolio_script.exists():
        error_msg = f"❌ Portfolio manager script not found: {portfolio_script}"
        print(error_msg)
        telegram_send(error_msg)
        return
    
    print(f"🚀 Running live portfolio manager: {portfolio_script}")
    
    try:
        # Run live_portfolio_manager.py from its directory
        result = subprocess.run(
            [sys.executable, str(portfolio_script)],
            cwd=str(portfolio_script.parent),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += f"\n\nERRORS:\n{result.stderr}"
        
        if result.returncode == 0:
            # Success - send output to Telegram
            message = f"✅ Live Portfolio Manager - Başarılı\n\n{output}"
            print(output)
            telegram_send(message)
        else:
            # Failed - send error
            error_msg = f"❌ Live Portfolio Manager - Hata (exit code: {result.returncode})\n\n{output}"
            print(error_msg)
            telegram_send(error_msg)
            
    except subprocess.TimeoutExpired:
        timeout_msg = "❌ Live Portfolio Manager - Timeout (5 dakikadan uzun sürdü)"
        print(timeout_msg)
        telegram_send(timeout_msg)
    except Exception as e:
        error_msg = f"❌ Live Portfolio Manager - Beklenmeyen hata:\n{str(e)}"
        print(error_msg)
        telegram_send(error_msg)

if __name__ == "__main__":
    main()
