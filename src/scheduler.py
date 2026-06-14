import time
import subprocess
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from api import app
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

def run_1h():
    logger.info("Running 1H Context Inference...")
    subprocess.run(["python3", "src/fetch_market_data.py", "--interval", "1h"])
    subprocess.run(["python3", "src/build_report.py"])

def run_1d():
    logger.info("Running 1D Execution Engine...")
    subprocess.run(["python3", "src/fetch_market_data.py", "--interval", "1d", "--use-1h-context"])
    subprocess.run(["python3", "src/build_report.py", "--title", "Daily Execution Report"])

def run_weekly():
    logger.info("Running Weekly Synthesis...")
    subprocess.run(["python3", "src/build_weekly_synthesis.py"])

def start_scheduler():
    scheduler = BackgroundScheduler()
    
    # Run 1H at minute 0 of every hour
    scheduler.add_job(run_1h, 'cron', minute=0)
    
    # Run 1D at midnight Monday through Friday
    scheduler.add_job(run_1d, 'cron', day_of_week='mon-fri', hour=0, minute=0)
    
    # Run weekly synthesis on Sunday at 8:00 AM
    scheduler.add_job(run_weekly, 'cron', day_of_week='sun', hour=8, minute=0)
    
    scheduler.start()
    logger.info("APScheduler started successfully.")

if __name__ == "__main__":
    start_scheduler()
    logger.info("Starting FastAPI server...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
