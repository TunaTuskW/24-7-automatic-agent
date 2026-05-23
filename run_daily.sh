#!/usr/bin/env bash
# run_daily.sh
# Pushes the most recent 72 hours roll to Discord

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==========================================="
echo "Running daily digest push: $(date)"
echo "==========================================="

LATEST_ROLL=$(ls -t reports/72\ hours\ roll\ *.md 2>/dev/null | head -n 1)

if [ -n "$LATEST_ROLL" ]; then
    echo "Pushing $LATEST_ROLL to Discord..."
    python3 src/push_to_discord.py "$LATEST_ROLL" DAILY
else
    echo "No 72 hours roll file found."
fi

echo "Daily complete!"
echo "==========================================="
