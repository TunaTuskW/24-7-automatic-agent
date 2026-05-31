#!/usr/bin/env bash
# run_weekly.sh
# Generates and pushes the weekly synthesis report

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==========================================="
echo "Running weekly synthesis pipeline: $(date)"
echo "==========================================="

echo "1) Fetching latest market data..."
PYTHONPATH=. python3 src/fetch_market_data.py --interval 1wk

echo "2) Building weekly synthesis and pushing to Discord..."
PYTHONPATH=. python3 src/build_weekly_synthesis.py

echo "Weekly complete!"
echo "==========================================="
