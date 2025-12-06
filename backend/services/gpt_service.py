"""
GPT Analysis Service
Reads and serves GPT portfolio analysis
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

# Path to GPT analysis output
GPT_ANALYSIS_PATH = Path(__file__).parent.parent.parent / "src" / "quanttrade" / "models_2.0" / "gpt_analysis_latest.json"


def get_latest_analysis() -> Optional[Dict]:
    """
    Read the latest GPT analysis from disk
    
    Returns:
        Dict with analysis data or None if file doesn't exist
    """
    if not GPT_ANALYSIS_PATH.exists():
        return None
    
    try:
        with open(GPT_ANALYSIS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return {
            "timestamp": data.get("timestamp"),
            "as_of_date": data.get("as_of_date"),
            "analysis": data.get("analysis"),
            "snapshot_ref": data.get("snapshot_ref")
        }
    except Exception as e:
        print(f"Error reading GPT analysis: {e}")
        return None


def format_for_telegram(analysis_data: Dict) -> str:
    """
    Format GPT analysis for Telegram display
    
    Args:
        analysis_data: Analysis dict from get_latest_analysis()
    
    Returns:
        Formatted markdown string for Telegram
    """
    if not analysis_data:
        return "❌ GPT analizi bulunamadı."
    
    timestamp = analysis_data.get("timestamp", "N/A")
    as_of_date = analysis_data.get("as_of_date", "N/A")
    analysis = analysis_data.get("analysis", "")
    
    # Parse timestamp for display
    try:
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%d.%m.%Y %H:%M")
    except:
        time_str = timestamp
    
    message = f"""
🤖 **GPT Portfolio Analizi**

📅 Tarih: {as_of_date}
🕒 Analiz: {time_str}

{analysis}
    """.strip()
    
    return message
