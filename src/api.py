import json
import os
import csv
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import asyncio
import aiofiles
import logging

app = FastAPI(title="QuantOS API")

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost,http://localhost:80,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QUANTOS_SECRET = os.environ.get("QUANTOS_API_SECRET", "")

def require_auth(x_api_key: str = Header(None)):
    if QUANTOS_SECRET and x_api_key != QUANTOS_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/decision")
def get_decision():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "trade_recommendation.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"recommended_action": "HOLD", "decision_rationale": "Pipeline not yet run."}

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
                    try:
                        await websocket.send_json({"type": "heartbeat", "ts": datetime.utcnow().isoformat()})
                    except Exception:
                        break
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
    state_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', 'market_snapshot.json')
    prior_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', 'market_snapshot_prior.json')
    
    for path in [state_path, prior_path]:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                pass
    return {"error": "Snapshot not found"}
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
        allocations = {"SPX_Kelly": float(kelly_obj)}
        spx_kelly = float(kelly_obj)
        safe_haven = 0.0
    else:
        allocations = kelly_obj
        spx_kelly = kelly_obj.get("SPX_Kelly", 0.0)
        safe_haven = kelly_obj.get("GLD_Kelly", 0.0)
    
    return {
        "status": "Active",
        "regime": dominant,
        "regimeProb": prob,
        "kelly": spx_kelly,
        "safeHaven": safe_haven,
        "allocations": allocations,
        "vix": data.get("raw_indicators", {}).get("VIX", {}).get("current", 0.0),
        "spread": ds_layer.get("features_vector", [0,0,0,0,0,0,0,0])[7],
        "lastUpdate": data.get("timestamp_utc", datetime.utcnow().isoformat())
    }

@app.get("/api/entry_quality")
def get_entry_quality():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', 'entry_quality.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"entry_score": None, "entry_bias": "FLAT", "computed_utc": None}

@app.get("/api/frequency")
def get_frequency():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'state', 'frequency_state.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"recommended_frequency": "4h", "score": 0, "reason": "No data yet", "evaluated_utc": None}

@app.get("/api/events/recent")
def get_recent_events(limit: int = 50):
    log_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'system_events.jsonl')
    events = []
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()
            for line in lines[-limit:]:
                if line.strip():
                    try:
                        obj = json.loads(line)
                        if obj.get("source") == "market_monitor":
                            events.append(obj)
                    except Exception:
                        pass
        except Exception as e:
            return {"error": str(e)}
    return {"events": list(reversed(events))}

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
            full_ledger = []
            with open(ledger_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    full_ledger.append(row)
            
            realized_pnl = 0.0
            cost_basis = {}
            
            for row in full_ledger:
                ticker = row.get('ticker')
                action = row.get('action')
                
                try:
                    shares = float(row.get('shares', 0))
                except ValueError:
                    shares = 0.0
                    
                # fallback if shares is missing
                try:
                    price = float(row.get('price', 0))
                    value = float(row.get('value', 0))
                except ValueError:
                    price = 0.0
                    value = 0.0
                    
                if shares == 0 and price > 0:
                    shares = value / price
                    
                if ticker not in cost_basis:
                    cost_basis[ticker] = {'qty': 0.0, 'cost': 0.0}
                    
                if action == 'BUY':
                    cost_basis[ticker]['qty'] += shares
                    cost_basis[ticker]['cost'] += value
                elif action == 'SELL':
                    if cost_basis[ticker]['qty'] > 1e-6:
                        fraction_sold = shares / cost_basis[ticker]['qty']
                        fraction_sold = min(1.0, fraction_sold)
                        cost_of_sold = cost_basis[ticker]['cost'] * fraction_sold
                        
                        cost_basis[ticker]['qty'] -= shares
                        cost_basis[ticker]['cost'] -= cost_of_sold
            
            # The remaining cost_basis is the cost of currently open positions
            total_open_cost = sum(v['cost'] for v in cost_basis.values() if v['qty'] > 1e-6)
            
            # Current value of open positions = Total Equity - Cash
            current_open_value = portfolio.get('total_equity', 10000.0) - portfolio.get('cash', 10000.0)
            
            unrealized_pnl = current_open_value - total_open_cost
            total_pnl = portfolio.get('total_equity', 10000.0) - 10000.0
            realized_pnl = total_pnl - unrealized_pnl
            
            # If no open positions, force unrealized to 0
            if abs(current_open_value) < 1.0:
                unrealized_pnl = 0.0
                realized_pnl = total_pnl
                
            portfolio['realized_pnl'] = realized_pnl
            portfolio['unrealized_pnl'] = unrealized_pnl

            # Return last 50 trades, reversed (newest first)
            ledger = full_ledger[-50:]
            ledger.reverse()
        except Exception as e:
            print(f"Error processing ledger: {e}")
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
        "regime": data.get("regime", {}),
        "trend_state": data.get("trend_state", {}),
        "smc_state": data.get("smc_state", {}),
        "session_state": data.get("session_state", {}),
        "liquidity_state": data.get("liquidity_state", {})
    }

@app.get("/api/macro", dependencies=[Depends(require_auth)])
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

@app.get("/api/settings", dependencies=[Depends(require_auth)])
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

@app.post("/api/settings", dependencies=[Depends(require_auth)])
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

@app.post("/api/trading_settings", dependencies=[Depends(require_auth)])
def update_trading_settings(payload: TradingSettingsPayload):
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'trading_settings.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump({"active_tickers": payload.active_tickers}, f)
    return {"status": "success"}

import yfinance as yf

@app.get("/api/chart/{ticker}")
def get_chart_data(ticker: str, interval: str = "1d"):
    try:
        # Map ticker to YF
        yf_map = {"SPX": "^GSPC", "BTC": "BTC-USD", "GLD": "GC=F", "WTI": "CL=F", "SH": "SH"}
        yf_ticker = yf_map.get(ticker.upper(), ticker.upper())
        
        data = yf.Ticker(yf_ticker)
        
        # Determine period based on interval
        if interval in ["1h", "60m"]:
            period = "60d"
        elif interval == "1wk":
            period = "2y"
        else:
            period = "180d"
            
        hist = data.history(period=period, interval=interval)
        
        chart_data = []
        for date, row in hist.iterrows():
            # For intraday, we need timestamp in seconds, for daily we need YYYY-MM-DD
            if interval in ["1h", "60m"]:
                time_val = int(date.timestamp())
            else:
                time_val = date.strftime('%Y-%m-%d')
                
            chart_data.append({
                "time": time_val,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "value": float(row["Volume"])  # Volume uses 'value' in lightweight-charts
            })
            
        return {"data": chart_data}
    except Exception as e:
        return {"error": str(e)}

class TriggerPayload(BaseModel):
    job: str
    start_date: str = None   # YYYY-MM-DD, optional
    end_date: str = None     # YYYY-MM-DD, optional

import subprocess
import logging
logger = logging.getLogger("api_trigger")

def run_job_background(job_type: str, start_date: str = None, end_date: str = None):
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
            cmd = ["python3", "src/quantitative_backtester.py", "--interval", "1d"]
            if start_date:
                cmd += ["--start-date", start_date]
            if end_date:
                cmd += ["--end-date", end_date]
            subprocess.run(cmd)
    except Exception as e:
        logger.error(f"Manual job {job_type} failed: {e}")

@app.post("/api/trigger", dependencies=[Depends(require_auth)])
def trigger_job(payload: TriggerPayload, background_tasks: BackgroundTasks):
    if payload.job not in ["1h", "1d", "1w", "weekly", "test"]:
        return {"error": "Invalid job type"}

    background_tasks.add_task(
        run_job_background,
        payload.job,
        payload.start_date,
        payload.end_date
    )
    return {
        "status": "success",
        "message": f"Job {payload.job} dispatched.",
        "start_date": payload.start_date,
        "end_date": payload.end_date
    }

@app.get("/api/reports", dependencies=[Depends(require_auth)])
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
