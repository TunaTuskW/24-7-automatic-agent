#!/usr/bin/env bash
# run_all.sh
# 100% deterministic, harmless script to build and push the 4-hour report

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==========================================="
echo "Running automated pipeline: $(date)"
echo "==========================================="

echo "1) Fetching market data..."
PYTHONPATH=. python3 src/fetch_market_data.py --interval 4h

echo "2) Building 4-hour report and pushing to Discord..."
PYTHONPATH=. python3 src/build_report.py

echo "Pipeline complete!"
echo "==========================================="
