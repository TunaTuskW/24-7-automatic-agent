import yfinance as yf
import pandas as pd
import requests
from typing import List
from src.interfaces.data_broker import DataBroker
from src.observability.logger import get_logger

logger = get_logger("yahoo-adapter")

class YahooAdapter(DataBroker):
    def __init__(self, fred_key: str = None):
        self.fred_key = fred_key

    def fetch_ohlcv_daily(self, tickers: List[str], period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        logger.info(f"Fetching OHLCV for {len(tickers)} tickers over {period} (interval: {interval})")
        try:
            raw_data = yf.download(tickers, period=period, interval=interval, group_by="ticker", progress=False, threads=True)
            return raw_data
        except Exception as e:
            logger.error(f"Failed to fetch daily OHLCV: {e}")
            return pd.DataFrame()
            
    def fetch_ohlcv_hourly(self, tickers: List[str], period: str = "5d") -> pd.DataFrame:
        logger.info(f"Fetching hourly OHLCV for {len(tickers)} tickers over {period}")
        try:
            raw_data = yf.download(tickers, period=period, interval="1h", group_by="ticker", progress=False, threads=True)
            return raw_data
        except Exception as e:
            logger.error(f"Failed to fetch hourly OHLCV: {e}")
            return pd.DataFrame()
            
    def fetch_yield(self, series_id: str) -> float:
        if not self.fred_key:
            logger.info(f"No FRED key. Falling back to Yahoo Finance for {series_id}")
            yf_ticker = "^TNX" if series_id == "DGS10" else "^FVX"
            try:
                tk = yf.Ticker(yf_ticker)
                hist = tk.history(period="1d")
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])
            except Exception as e:
                logger.error(f"Yahoo fallback failed for {yf_ticker}: {e}")
            return 0.0
            
        logger.info(f"Fetching FRED yield for {series_id}")
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={self.fred_key}&file_type=json"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            obs = data.get("observations", [])
            for ob in reversed(obs):
                val = ob.get("value", ".")
                if val != ".":
                    return float(val)
            return 0.0
        except Exception as e:
            logger.error(f"FRED fetch failed for {series_id}: {e}")
            return 0.0

    def fetch_yield_history(self, series_id: str, period: str = "90d") -> pd.Series:
        if not self.fred_key:
            yf_ticker = "^TNX" if series_id == "DGS10" else "^FVX"
            try:
                tk = yf.Ticker(yf_ticker)
                hist = tk.history(period=period)
                return hist['Close'].dropna()
            except Exception:
                return pd.Series(dtype=float)
                
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={self.fred_key}&file_type=json"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            obs = [(o["date"], float(o["value"])) for o in data.get("observations", []) if o["value"] != "."]
            s = pd.Series(dict(obs), dtype=float)
            s.index = pd.to_datetime(s.index)
            # return roughly the last 60 trading days
            return s.tail(65)
        except Exception:
            return pd.Series(dtype=float)
