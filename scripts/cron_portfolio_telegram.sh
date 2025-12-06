#!/bin/bash
# Portfolio Report Telegram Broadcast
# Runs at 21:35 (5 min after portfolio V2)

cd /root/Quanttrade

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:/root/Quanttrade:$PYTHONPATH

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Broadcast portfolio report
echo "[$(date)] Broadcasting portfolio report to Telegram..."
python3 live-telegram/portfolio_daily_sender.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] Portfolio report broadcast completed successfully"
else
    echo "[$(date)] Portfolio report broadcast failed with exit code $exit_code"
fi

exit $exit_code
