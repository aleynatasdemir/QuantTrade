#!/bin/bash
# GPT Telegram Broadcast
# Runs at 09:50 every weekday

cd /root/Quanttrade

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:/root/Quanttrade:$PYTHONPATH

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Broadcast GPT analysis
echo "[$(date)] Broadcasting GPT analysis to Telegram..."
python3 live-telegram/gpt_daily_sender.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] Telegram broadcast completed successfully"
else
    echo "[$(date)] Telegram broadcast failed with exit code $exit_code"
fi

exit $exit_code
