#!/bin/bash
# VDS Portfolio V2 Daily Runner
# Runs at 21:30 every weekday

cd /root/Quanttrade

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:$PYTHONPATH

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run portfolio V2
echo "[$(date)] Starting Portfolio V2..."
python3 src/quanttrade/models_2.0/live_portfolio_v2.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] Portfolio V2 completed successfully"
else
    echo "[$(date)] Portfolio V2 failed with exit code $exit_code"
fi

exit $exit_code
