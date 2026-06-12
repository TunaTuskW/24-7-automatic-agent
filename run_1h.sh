#!/usr/bin/env bash
# run_all.sh
# 100% deterministic, harmless script to build and push the 1-hour report

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==========================================="
echo "Running automated pipeline: $(date)"
echo "==========================================="

echo "1) Fetching market data..."
PYTHONPATH=. python3 src/fetch_market_data.py --interval 1h

echo "2) Building 1-hour report and pushing to Discord..."
PYTHONPATH=. python3 src/build_report.py

echo "3) Generating performance visual dashboard..."
PYTHONPATH=. python3 src/visualize_paper_trading.py

echo "Pipeline complete!"
echo "==========================================="
