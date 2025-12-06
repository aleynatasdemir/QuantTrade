#!/bin/bash
# GPT Snapshot Generator
# Runs at 09:40 every weekday

cd /root/Quanttrade/src/quanttrade/models_2.0

# Activate virtual environment
source /root/Quanttrade/.venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:$PYTHONPATH

# Load environment variables
if [ -f /root/Quanttrade/.env ]; then
    export $(cat /root/Quanttrade/.env | grep -v '^#' | xargs)
fi

# Run GPT snapshot
echo "[$(date)] Generating GPT snapshot..."
python3 gpt_snapshot.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] GPT snapshot generated successfully"
else
    echo "[$(date)] GPT snapshot failed with exit code $exit_code"
fi

exit $exit_code
