#!/bin/bash
# Full Pipeline Runner - Weekly (Sunday 16:00)
# Runs data download + feature engineering + model training

cd /root/Quanttrade

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:$PYTHONPATH

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run full pipeline
echo "[$(date)] Starting full pipeline (data + features + model training)..."
python3 run_daily_pipeline.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] Full pipeline completed successfully"
else
    echo "[$(date)] Full pipeline failed with exit code $exit_code"
fi

exit $exit_code
