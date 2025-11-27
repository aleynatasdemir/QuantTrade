#!/bin/bash
# GPT Analysis Runner
# Runs at 09:45 every weekday

cd /root/Quanttrade/src/quanttrade/models_2.0

# Activate virtual environment
source /root/Quanttrade/.venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/root/Quanttrade/src:$PYTHONPATH

# Load environment variables
if [ -f /root/Quanttrade/.env ]; then
    export $(cat /root/Quanttrade/.env | grep -v '^#' | xargs)
fi

# Run GPT analysis
echo "[$(date)] Running GPT analysis..."
python3 gpt_analyze.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date)] GPT analysis completed successfully"
    echo "[$(date)] Output saved to: gpt_analysis_latest.json"
else
    echo "[$(date)] GPT analysis failed with exit code $exit_code"
fi

exit $exit_code
