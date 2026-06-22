import time
import json
import os
import subprocess
from datetime import datetime, timezone
from src.engines.market_event_detector import MarketEventDetector
from src.observability.logger import get_logger

logger = get_logger("market-monitor")

POLL_INTERVAL_SECONDS = 300  # 5 minutes
STATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'state')
COOLDOWN_SECONDS = 1800  # Do not fire more than once per 30 min from events

def load_state(filename: str) -> dict:
    path = os.path.join(STATE_PATH, filename)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def run_monitor():
    detector = MarketEventDetector()
    last_event_trigger_time = 0

    logger.info("Market monitor started. Polling every 5 minutes.")

    while True:
        try:
            now = datetime.now(timezone.utc)
            now_ts = now.timestamp()

            # Load current state
            snapshot = load_state("market_snapshot.json")
            entry_quality = load_state("entry_quality.json")
            portfolio = {}
            portfolio_path = os.path.join(STATE_PATH, '..', 'paper_trading', 'paper_portfolio.json')
            if os.path.exists(portfolio_path):
                with open(portfolio_path, 'r') as f:
                    portfolio = json.load(f)

            current_vix_zscore = (
                snapshot.get("market_extremes_insight", {}).get("temperature_zscore", 0.0)
            )
            current_entry_score = entry_quality.get("entry_score", 0.5)
            positions = portfolio.get("positions", {})
            position_details = portfolio.get("position_details", {})

            # Fetch live prices
            active_assets = list(positions.keys())
            prices = detector.fetch_current_prices(active_tickers=active_assets)
            if not prices:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            # Detect events
            events = detector.detect(
                prices=prices,
                current_entry_score=current_entry_score,
                current_vix_zscore=current_vix_zscore,
                portfolio_positions=positions,
                portfolio_position_details=position_details
            )

            if events:
                logger.info(f"Detected {len(events)} market event(s): {[e['type'] for e in events]}")

                # Write events to event log for frontend WebSocket
                event_log_path = os.path.join(STATE_PATH, '..', 'logs', 'system_events.jsonl')
                os.makedirs(os.path.dirname(event_log_path), exist_ok=True)
                
                # Import webhook logic locally to avoid circular dependencies if any
                from src.push_to_discord import get_webhook_url, post_with_retry
                webhook_url = get_webhook_url()
                
                with open(event_log_path, 'a') as f:
                    for event in events:
                        event["timestamp"] = now.isoformat()
                        event["source"] = "market_monitor"
                        f.write(json.dumps(event) + "\n")
                        
                        if webhook_url and event.get("severity") in ["CRITICAL", "ELEVATED"]:
                            color = 16711680 if event.get("severity") == "CRITICAL" else 16753920
                            embed = {
                                "title": f"🚨 {event.get('type')} Detected",
                                "description": event.get('detail'),
                                "color": color,
                                "timestamp": now.isoformat()
                            }
                            post_with_retry(webhook_url, json={"embeds": [embed]})

                # Check cooldown before triggering pipeline
                should_run, interval, reason = detector.should_trigger_pipeline(events)

                if should_run and (now_ts - last_event_trigger_time) > COOLDOWN_SECONDS:
                    logger.info(f"Event trigger firing pipeline (interval={interval}): {reason}")
                    subprocess.run(["python3", "src/fetch_market_data.py", "--interval", interval])
                    last_event_trigger_time = now_ts
                elif should_run:
                    cooldown_remaining = int(COOLDOWN_SECONDS - (now_ts - last_event_trigger_time))
                    logger.info(f"Event trigger suppressed by cooldown ({cooldown_remaining}s remaining).")

        except Exception as e:
            logger.error(f"Market monitor error: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    run_monitor()
