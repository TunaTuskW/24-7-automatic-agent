import time
import subprocess
import logging
import json
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from src.api import app
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

FREQUENCY_STATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', 'frequency_state.json')

scheduler = BackgroundScheduler()
current_frequency = "4h"

import fcntl

def run_locked_subprocess(args, lock_name="execution.lock"):
    lock_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', lock_name)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, 'w') as lock_file:
        try:
            logger.info(f"Waiting for lock on {lock_name} for {' '.join(args)}...")
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            subprocess.run(args)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)

def run_1h():
    logger.info("Running 1H Context Layer (entry scoring + state write — no execution)...")
    run_locked_subprocess(["python3", "src/fetch_market_data.py", "--interval", "1h"])
    _apply_adaptive_frequency()

def run_4h():
    logger.info("Running 4H Execution Engine...")
    run_locked_subprocess(["python3", "src/fetch_market_data.py", "--interval", "4h"])
    subprocess.run(["python3", "src/build_report.py", "--title", "4H Execution Report"])
    _apply_adaptive_frequency()

def run_1d():
    logger.info("Running 1D Execution Engine...")
    run_locked_subprocess(["python3", "src/fetch_market_data.py", "--interval", "1d", "--use-1h-context"])
    subprocess.run(["python3", "src/build_report.py", "--title", "Daily Execution Report"])
    _apply_adaptive_frequency()

def run_weekly():
    logger.info("Running Weekly Synthesis...")
    run_locked_subprocess(["python3", "src/build_weekly_synthesis.py"])

def _apply_adaptive_frequency():
    global current_frequency
    try:
        if os.path.exists(FREQUENCY_STATE_PATH):
            with open(FREQUENCY_STATE_PATH, 'r') as f:
                state = json.load(f)
                recommended = state.get("recommended_frequency", "4h")
                
                if recommended != current_frequency:
                    logger.info(f"Adaptive Scheduler: Shifting frequency from {current_frequency} to {recommended}")
                    current_frequency = recommended
                    
                    if scheduler.get_job('main_execution'):
                        scheduler.remove_job('main_execution')
                        
                    from datetime import datetime
                    if current_frequency == "1h":
                        if scheduler.get_job('1h_context_scorer'):
                            scheduler.pause_job('1h_context_scorer')
                        scheduler.add_job(run_1h, 'cron', minute=0, id='main_execution', misfire_grace_time=3600, next_run_time=datetime.now())
                    elif current_frequency == "4h":
                        if scheduler.get_job('1h_context_scorer'):
                            scheduler.resume_job('1h_context_scorer')
                        scheduler.add_job(run_4h, 'cron', hour='0,4,8,12,16,20', minute=5, id='main_execution', misfire_grace_time=3600, next_run_time=datetime.now())
                    else:
                        if scheduler.get_job('1h_context_scorer'):
                            scheduler.resume_job('1h_context_scorer')
                        scheduler.add_job(run_1d, 'cron', hour=0, minute=0, id='main_execution', misfire_grace_time=3600, next_run_time=datetime.now())
    except Exception as e:
        logger.error(f"Failed to apply adaptive frequency: {e}")

def start_scheduler():
    # Base jobs that always run
    scheduler.add_job(run_1h, 'cron', minute=0, id='1h_context_scorer', misfire_grace_time=3600)
    scheduler.add_job(run_weekly, 'cron', day_of_week='sun', hour=8, minute=0, id='weekly', misfire_grace_time=3600)
    
    # Adaptive execution job starts at 4H
    scheduler.add_job(run_4h, 'cron', hour='0,4,8,12,16,20', minute=5, id='main_execution', misfire_grace_time=3600)
    
    scheduler.start()
    logger.info("APScheduler started successfully with adaptive frequency.")

def start_monitor_thread():
    """Run market monitor in a daemon thread."""
    from src.market_monitor import run_monitor
    import threading
    t = threading.Thread(target=run_monitor, daemon=True)
    t.start()
    logger.info("Market monitor thread started.")

if __name__ == "__main__":
    start_scheduler()
    start_monitor_thread()
    logger.info("Starting FastAPI server...")
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000)
