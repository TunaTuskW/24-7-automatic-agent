import json
import os
import csv
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import asyncio
import aiofiles
import logging

app = FastAPI(title="QuantOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/api/ws/pipeline")
async def websocket_pipeline(websocket: WebSocket):
    await websocket.accept()
    log_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'system_events.jsonl')
    
    # Check if file exists, if not wait
    while not os.path.exists(log_file):
        await asyncio.sleep(1)

    try:
        async with aiofiles.open(log_file, mode='r') as f:
            # Seek to end
            await f.seek(0, 2)
            
            while True:
                line = await f.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    event = json.loads(line)
                    await websocket.send_json(event)
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket Error: {e}")

def get_latest_snapshot():
    state_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', 'market_snapshot_prior.json')
    if os.path.exists(state_path):
        try:
            with open(state_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Snapshot not found"}

@app.get("/api/snapshot")
def get_snapshot():
    data = get_latest_snapshot()
    if "error" in data:
        return {"status": "Waiting for Engine", "regime": "UNKNOWN", "regimeProb": 0.0, "kelly": 0.0, "safeHaven": 0.0, "vix": 0.0, "spread": 0.0, "lastUpdate": datetime.utcnow().isoformat()}
    
    regime_data = data.get("regime", {})
    probs = regime_data.get("probabilities", {})
    dominant = regime_data.get("dominant_regime", "UNKNOWN")
    prob = probs.get(dominant, 0.0)
    
    # Kelly allocations are inside data_science_layer -> epistemic_metrics -> kelly_exposure_fraction
    ds_layer = data.get("data_science_layer", {})
    epistemic = ds_layer.get("epistemic_metrics", {})
    kelly_obj = epistemic.get("kelly_exposure_fraction", {})
    if isinstance(kelly_obj, (float, int)):
        spx_kelly = float(kelly_obj)
        safe_haven = 0.0
    else:
        spx_kelly = kelly_obj.get("SPX_Kelly", 0.0)
        safe_haven = kelly_obj.get("GLD_Kelly", 0.0)
    
    raw_indicators = data.get("raw_indicators", {})
    bonds = data.get("bonds", {})
    
    vix = raw_indicators.get("VIX", {}).get("current", 0.0)
    spread = bonds.get("2s10s_spread", 0.0)
    
    return {
        "status": "Active",
        "regime": dominant,
        "regimeProb": prob,
        "kelly": spx_kelly,
        "safeHaven": safe_haven,
        "vix": vix,
        "spread": spread,
        "lastUpdate": data.get("generated_utc", datetime.utcnow().isoformat())
    }

@app.get("/api/portfolio")
def get_portfolio(type: str = "live"):
    base_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'paper_trading')
    
    if type == "backtest":
        portfolio_path = os.path.join(base_dir, 'backtest_portfolio.json')
        ledger_path = os.path.join(base_dir, 'backtest_ledger.csv')
    else:
        portfolio_path = os.path.join(base_dir, 'paper_portfolio.json')
        ledger_path = os.path.join(base_dir, 'paper_ledger.csv')
    
    portfolio = {
        "cash": 10000.0,
        "positions": {},
        "total_equity": 10000.0,
        "last_update": datetime.utcnow().isoformat()
    }
    
    if os.path.exists(portfolio_path):
        try:
            with open(portfolio_path, 'r') as f:
                portfolio = json.load(f)
        except Exception:
            pass
            
    ledger = []
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ledger.append(row)
            # Return last 50 trades, reversed (newest first)
            ledger = ledger[-50:]
            ledger.reverse()
        except Exception:
            pass
            
    return {
        "portfolio": portfolio,
        "ledger": ledger
    }

@app.get("/api/model")
def get_model():
    data = get_latest_snapshot()
    if "error" in data:
        return data
        
    return {
        "data_science_layer": data.get("data_science_layer", {}),
        "kalman_state": data.get("kalman_state", {}),
        "mlp_deep_state": data.get("mlp_deep_state", {}),
        "mcs": data.get("mcs", {}),
        "regime": data.get("regime", {})
    }

@app.get("/api/macro")
def get_macro():
    data = get_latest_snapshot()
    if "error" in data:
        return data
        
    return {
        "news_signal": data.get("news_signal", {}),
        "economic_calendar": data.get("economic_calendar", {})
    }

@app.get("/api/logs")
def get_logs():
    log_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'system_events.jsonl')
    logs = []
    
    if os.path.exists(log_path):
        try:
            # Read all lines
            with open(log_path, 'r') as f:
                lines = f.readlines()
            
            # Take last 200 lines
            for line in lines[-200:]:
                if line.strip():
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
        except Exception as e:
            return {"error": str(e)}
            
    return {"logs": logs}

from pydantic import BaseModel

class SettingsPayload(BaseModel):
    gemini_key: str = None
    fred_key: str = None
    discord_webhook: str = None

def mask_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"

def read_config_file(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), '..', 'config', filename)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read().strip()
    return ""

def write_config_file(filename: str, content: str):
    path = os.path.join(os.path.dirname(__file__), '..', 'config', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content.strip())

@app.get("/api/settings")
def get_settings():
    gemini = read_config_file('gemini_api_key.txt')
    fred = read_config_file('fred_api_key.txt')
    webhook = read_config_file('webhook_config.txt')
    
    return {
        "gemini_key_masked": mask_key(gemini) if gemini else "",
        "fred_key_masked": mask_key(fred) if fred else "",
        "discord_webhook_masked": mask_key(webhook) if webhook else "",
        "has_gemini": bool(gemini),
        "has_fred": bool(fred),
        "has_webhook": bool(webhook)
    }

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    # Only overwrite if a new non-empty value was provided
    if payload.gemini_key:
        write_config_file('gemini_api_key.txt', payload.gemini_key)
    if payload.fred_key:
        write_config_file('fred_api_key.txt', payload.fred_key)
    if payload.discord_webhook:
        write_config_file('webhook_config.txt', payload.discord_webhook)
        
    return {"status": "success"}

class TradingSettingsPayload(BaseModel):
    active_tickers: list

@app.get("/api/trading_settings")
def get_trading_settings():
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'trading_settings.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"active_tickers": ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]}

@app.post("/api/trading_settings")
def update_trading_settings(payload: TradingSettingsPayload):
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'trading_settings.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump({"active_tickers": payload.active_tickers}, f)
    return {"status": "success"}

import yfinance as yf

@app.get("/api/chart/{ticker}")
def get_chart_data(ticker: str):
    try:
        # Map ticker to YF
        yf_map = {"SPX": "^GSPC", "BTC": "BTC-USD", "GLD": "GC=F", "WTI": "CL=F", "SH": "SH"}
        yf_ticker = yf_map.get(ticker.upper(), ticker.upper())
        
        data = yf.Ticker(yf_ticker)
        hist = data.history(period="180d", interval="1d")
        
        chart_data = []
        for date, row in hist.iterrows():
            chart_data.append({
                "time": date.strftime('%Y-%m-%d'),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"])
            })
            
        return {"data": chart_data}
    except Exception as e:
        return {"error": str(e)}

class TriggerPayload(BaseModel):
    job: str

import subprocess
import logging
logger = logging.getLogger("api_trigger")

def run_job_background(job_type: str):
    try:
        if job_type == "1h":
            logger.info("Running 1H Context Inference manually...")
            subprocess.run(["python3", "src/fetch_market_data.py", "--interval", "1h"])
            subprocess.run(["python3", "src/build_report.py"])
        elif job_type == "1d":
            logger.info("Running 1D Execution Engine manually...")
            subprocess.run(["python3", "src/fetch_market_data.py", "--interval", "1d", "--use-1h-context"])
            subprocess.run(["python3", "src/build_report.py", "--title", "Daily Execution Report"])
        elif job_type == "1w":
            logger.info("Running 1W Execution Engine and Weekly Synthesis manually...")
            subprocess.run(["python3", "src/fetch_market_data.py", "--interval", "1wk"])
            subprocess.run(["python3", "src/build_report.py", "--title", "Weekly Execution Report"])
            subprocess.run(["python3", "src/build_weekly_synthesis.py"])
        elif job_type == "test":
            logger.info("Running Quantitative Backtester manually...")
            subprocess.run(["python3", "src/quantitative_backtester.py", "--interval", "1d"])
    except Exception as e:
        logger.error(f"Manual job {job_type} failed: {e}")

@app.post("/api/trigger")
def trigger_job(payload: TriggerPayload, background_tasks: BackgroundTasks):
    if payload.job not in ["1h", "1d", "1w", "weekly", "test"]:
        return {"error": "Invalid job type"}
    
    background_tasks.add_task(run_job_background, payload.job)
    return {"status": "success", "message": f"Job {payload.job} dispatched to background."}

@app.get("/api/reports")
def get_reports_list():
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    updates_dir = os.path.join(reports_dir, 'updates')
    
    files = []
    
    def scan_dir(d, prefix=""):
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith('.md'):
                    stat = os.stat(os.path.join(d, f))
                    files.append({
                        "filename": prefix + f,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    })
    
    scan_dir(reports_dir)
    scan_dir(updates_dir, prefix="updates/")
    
    # Sort newest first
    files.sort(key=lambda x: x["mtime"], reverse=True)
    
    return {"reports": files}

# Mount the static reports directory
reports_path = os.path.join(os.path.dirname(__file__), '..', 'reports')
if os.path.exists(reports_path):
    app.mount("/reports", StaticFiles(directory=reports_path), name="reports")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
