#!/usr/bin/env python3
"""
fetch_market_data.py
Pulls structured market data from yfinance, FRED, and ECB Data Portal.
Writes market_snapshot.json for the macro briefing agent to consume.
Run before each 4-hour briefing cycle.
"""

import os
import json
import logging
import requests
import numpy as np
from datetime import datetime, timezone, timedelta

try:
    import yfinance as yf
except ImportError:
    raise ImportError("Install yfinance: pip install yfinance --break-system-packages")

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), '..', 'logs', 'fetch_market_data.log'),
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)

def get_fred_key():
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'fred_api_key.txt')
    if os.path.exists(path):
        with open(path, 'r') as f:
            key = f.read().strip()
            if key and not key.startswith("PASTE"):
                return key
    return None

ROLLING_DAYS = 5

EQUITY_TICKERS = {
    "SPX":   "^GSPC",
    "NDX":   "^NDX",
    "DAX":   "^GDAXI",
    "FTSE":  "^FTSE",
    "N225":  "^N225",
    "HSI":   "^HSI",
}

ENERGY_TICKERS = {
    "WTI":   "CL=F",
    "Brent": "BZ=F",
    "TTF":   "TTF=F",
}

FX_TICKERS = {
    "DXY":    "DX=F",
    "EURUSD": "EURUSD=X",
}

def compute_stats(series):
    if series is None or len(series) < 2:
        return None
    current  = float(series.iloc[-1])
    prev     = float(series.iloc[-2])
    delta    = current - prev
    delta_pct = (delta / prev * 100) if prev != 0 else 0
    rolling  = series.tail(ROLLING_DAYS)
    mean     = float(rolling.mean())
    std      = float(rolling.std()) if len(rolling) > 1 else 0
    z_score  = ((current - mean) / std) if std != 0 else 0
    if len(rolling) >= 3:
        slope    = float(np.polyfit(range(len(rolling)), rolling.values, 1)[0])
        momentum = "up" if slope > 0 else "down" if slope < 0 else "flat"
    else:
        momentum = "flat"
    return {
        "current":   round(current, 4),
        "prev":      round(prev, 4),
        "delta":     round(delta, 4),
        "delta_pct": round(delta_pct, 3),
        "mean_5d":   round(mean, 4),
        "std_5d":    round(std, 4),
        "z_score":   round(z_score, 3),
        "momentum":  momentum,
    }

def fetch_yfinance(tickers_dict, label):
    results = {}
    for name, ticker in tickers_dict.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="10d", interval="1d")
            if hist.empty:
                logging.warning(f"yfinance: no data for {name} ({ticker})")
                results[name] = None
                continue
            stats = compute_stats(hist["Close"])
            results[name] = stats
            logging.info(f"yfinance: {name} = {stats['current']}")
        except Exception as e:
            logging.error(f"yfinance error for {name}: {e}")
            results[name] = None
    return results

def fetch_fred_yield(series_id, fred_key):
    if not fred_key:
        logging.warning(f"FRED key not set. Skipping {series_id}.")
        return None
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id":        series_id,
            "api_key":          fred_key,
            "file_type":        "json",
            "sort_order":       "desc",
            "limit":            ROLLING_DAYS + 3,
            "observation_start": (
                datetime.now(timezone.utc) - timedelta(days=14)
            ).strftime("%Y-%m-%d"),
        }
        response = requests.get(url, params=params, timeout=10, verify=True)
        response.raise_for_status()
        data = response.json()
        obs  = [
            float(o["value"])
            for o in reversed(data["observations"])
            if o["value"] != "."
        ]
        if len(obs) < 2:
            logging.warning(f"FRED: insufficient data for {series_id}")
            return None
        import pandas as pd
        series = pd.Series(obs)
        stats  = compute_stats(series)
        logging.info(f"FRED: {series_id} = {stats['current']}")
        return stats
    except Exception as e:
        logging.error(f"FRED error for {series_id}: {e}")
        return None

def fetch_ecb_bund_10y():
    try:
        url = (
            "https://data-api.ecb.europa.eu/service/data/"
            "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
            "?format=jsondata&lastNObservations=10"
        )
        headers  = {"Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10, verify=True)
        response.raise_for_status()
        data   = response.json()
        obs    = data["dataSets"][0]["series"]["0:0:0:0:0:0:0"]["observations"]
        values = [float(v[0]) for k, v in sorted(
            obs.items(), key=lambda x: int(x[0])
        ) if v[0] is not None]
        if len(values) < 2:
            logging.warning("ECB: insufficient Bund 10Y data")
            return None
        import pandas as pd
        series = pd.Series(values)
        stats  = compute_stats(series)
        logging.info(f"ECB: Bund10Y = {stats['current']}")
        return stats
    except Exception as e:
        logging.error(f"ECB Bund 10Y error: {e}")
        return None

def compute_cross_asset_flags(snapshot):
    flags = []
    spx   = snapshot.get("equities", {}).get("SPX")
    us10y = snapshot.get("bonds", {}).get("US10Y")
    wti   = snapshot.get("energy", {}).get("WTI")
    dxy   = snapshot.get("fx", {}).get("DXY")
    if not spx or not us10y:
        return flags
    spx_move   = spx["delta_pct"]
    yield_move = us10y["delta"]
    if spx_move < -1.0 and yield_move > 0.05:
        flags.append(
            "CROSS-ASSET: Equities and bonds selling simultaneously — "
            "no safe haven bid. Potential liquidity or regime event."
        )
    if dxy and dxy["delta_pct"] > 0.3 and spx_move > 0.5:
        flags.append(
            "CROSS-ASSET: USD strengthening alongside rising equities — "
            "divergence from standard risk-on behavior."
        )
    if wti and wti["delta_pct"] > 1.5 and spx_move < -0.5:
        flags.append(
            "CROSS-ASSET: Energy spiking alongside equity selloff — "
            "stagflation signal."
        )
    if abs(spx["z_score"]) > 2.0:
        flags.append(
            f"STAT FLAG: SPX move is {spx['z_score']:.1f} standard deviations "
            f"from 5-day mean — statistically significant."
        )
    if abs(us10y["z_score"]) > 2.0:
        flags.append(
            f"STAT FLAG: US10Y move is {us10y['z_score']:.1f} standard deviations "
            f"from 5-day mean — statistically significant."
        )
    return flags

def compute_data_driven_escalation(snapshot, flags):
    spx   = snapshot.get("equities", {}).get("SPX")
    us10y = snapshot.get("bonds", {}).get("US10Y")
    tier  = "ROUTINE"
    if spx:
        move = abs(spx["delta_pct"])
        if move > 2.0:
            tier = "CRITICAL"
        elif move > 1.0:
            tier = "ELEVATED"
    if us10y:
        yield_change_bps = abs(us10y["delta"]) * 100
        if yield_change_bps > 20:
            tier = "CRITICAL"
        elif yield_change_bps > 10 and tier != "CRITICAL":
            tier = "ELEVATED"
    if any("CROSS-ASSET" in f for f in flags) and tier == "ROUTINE":
        tier = "ELEVATED"
    return tier

def main():
    logging.info("=== fetch_market_data.py starting ===")
    fred_key = get_fred_key()
    snapshot = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "equities":      fetch_yfinance(EQUITY_TICKERS, "equities"),
        "energy":        fetch_yfinance(ENERGY_TICKERS, "energy"),
        "fx":            fetch_yfinance(FX_TICKERS, "fx"),
        "bonds": {
            "US2Y":    fetch_fred_yield("DGS2", fred_key),
            "US10Y":   fetch_fred_yield("DGS10", fred_key),
            "Bund10Y": fetch_ecb_bund_10y(),
        },
    }
    us2y  = snapshot["bonds"]["US2Y"]
    us10y = snapshot["bonds"]["US10Y"]
    if us2y and us10y:
        spread = round(us10y["current"] - us2y["current"], 4)
        snapshot["bonds"]["spread_2s10s"] = spread
        logging.info(f"2s10s spread: {spread}")
    flags      = compute_cross_asset_flags(snapshot)
    escalation = compute_data_driven_escalation(snapshot, flags)
    snapshot["cross_asset_flags"]      = flags
    snapshot["data_driven_escalation"] = escalation
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_snapshot.json')
    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2)
    logging.info(f"Snapshot written: {output_path}")
    logging.info(f"Escalation tier: {escalation}")
    print(f"[OK] market_snapshot.json written — tier: {escalation}")

if __name__ == "__main__":
    main()
