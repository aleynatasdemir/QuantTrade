#!/bin/bash
# Daily Data Download Runner
# Runs at 19:00 every weekday

cd /root/Quanttrade

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:$PYTHONPATH

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run daily data download
echo "[$(date)] Starting daily data download..."
python3 run_daily_prices.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] Data download completed successfully"
else
    echo "[$(date)] Data download failed with exit code $exit_code"
fi

exit $exit_code
