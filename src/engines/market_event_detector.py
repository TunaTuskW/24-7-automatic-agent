import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone, timedelta
from src.observability.logger import get_logger

logger = get_logger("market-event-detector")

class MarketEventDetector:
    """
    Polls market data every N minutes and classifies events.
    Returns a list of active events and a recommended action.
    """

    PRICE_SHOCK_THRESHOLD  = 0.015   # 1.5% move in 30 min
    VIX_SPIKE_THRESHOLD    = 0.10    # 10% VIX rise in 60 min
    REGIME_STRESS_VIX_Z    = 2.0     # VIX z-score crossing this level
    ENTRY_FLIP_LOW         = 0.35
    ENTRY_FLIP_HIGH        = 0.65
    STOP_APPROACH_BUFFER   = 0.01    # 1% buffer before trailing stop

    def __init__(self):
        self._last_spx_price = None
        self._last_vix_price = None
        self._last_check_utc = None
        self._last_entry_score = 0.5

    def fetch_current_prices(self) -> dict:
        """Fetches current SPX and VIX prices using minimal yfinance call."""
        try:
            data = yf.download(
                ["^GSPC", "^VIX"],
                period="1d",
                interval="5m",
                progress=False,
                threads=False
            )
            # If multiple tickers, columns are MultiIndex: (Price, Ticker) -> data["Close"]["^GSPC"]
            if isinstance(data.columns, pd.MultiIndex):
                spx_close = data["Close"]["^GSPC"].dropna()
                vix_close = data["Close"]["^VIX"].dropna()
            else:
                # If only one ticker somehow, or flattened
                spx_close = data["Close"].dropna()
                vix_close = data["Close"].dropna()
                
            return {
                "spx_now": float(spx_close.iloc[-1]) if len(spx_close) > 0 else None,
                "spx_30m_ago": float(spx_close.iloc[-7]) if len(spx_close) >= 7 else None,
                "vix_now": float(vix_close.iloc[-1]) if len(vix_close) > 0 else None,
                "vix_60m_ago": float(vix_close.iloc[-13]) if len(vix_close) >= 13 else None,
                "vix_series": vix_close
            }
        except Exception as e:
            logger.error(f"MarketEventDetector price fetch failed: {e}")
            return {}

    def detect(
        self,
        prices: dict,
        current_entry_score: float,
        current_vix_zscore: float,
        portfolio_positions: dict,
        portfolio_position_details: dict
    ) -> list:
        """
        Returns list of detected event dicts.
        Each event: {"type": str, "severity": "CRITICAL"|"ELEVATED"|"ROUTINE", "detail": str}
        """
        events = []
        spx_now      = prices.get("spx_now")
        spx_30m_ago  = prices.get("spx_30m_ago")
        vix_now      = prices.get("vix_now")
        vix_60m_ago  = prices.get("vix_60m_ago")

        # 1. Price Shock
        if spx_now and spx_30m_ago and spx_30m_ago > 0:
            move_30m = abs((spx_now - spx_30m_ago) / spx_30m_ago)
            if move_30m >= self.PRICE_SHOCK_THRESHOLD:
                severity = "CRITICAL" if move_30m > 0.025 else "ELEVATED"
                events.append({
                    "type": "PRICE_SHOCK",
                    "severity": severity,
                    "detail": f"SPX moved {move_30m:.2%} in 30 min"
                })
                logger.warning(f"PRICE_SHOCK detected: {move_30m:.2%} in 30 min")

        # 2. Volatility Spike
        if vix_now and vix_60m_ago and vix_60m_ago > 0:
            vix_rise = (vix_now - vix_60m_ago) / vix_60m_ago
            if vix_rise >= self.VIX_SPIKE_THRESHOLD:
                events.append({
                    "type": "VOLATILITY_SPIKE",
                    "severity": "ELEVATED",
                    "detail": f"VIX rose {vix_rise:.2%} in 60 min"
                })
                logger.warning(f"VOLATILITY_SPIKE detected: VIX {vix_60m_ago:.1f} -> {vix_now:.1f}")

        # 3. Regime Stress
        if current_vix_zscore >= self.REGIME_STRESS_VIX_Z:
            events.append({
                "type": "REGIME_STRESS",
                "severity": "CRITICAL",
                "detail": f"VIX z-score at {current_vix_zscore:.2f}"
            })

        # 4. Entry Flip (opportunity opened)
        if self._last_entry_score < self.ENTRY_FLIP_LOW and current_entry_score >= self.ENTRY_FLIP_HIGH:
            events.append({
                "type": "ENTRY_FLIP",
                "severity": "ROUTINE",
                "detail": f"Entry score flipped from {self._last_entry_score:.2f} to {current_entry_score:.2f}"
            })
            logger.info(f"ENTRY_FLIP detected: score {self._last_entry_score:.2f} -> {current_entry_score:.2f}")
        self._last_entry_score = current_entry_score

        # 5. Stop Approach
        if spx_now and portfolio_positions and portfolio_position_details:
            for ticker, shares in portfolio_positions.items():
                if shares > 0 and ticker in portfolio_position_details:
                    peak = portfolio_position_details[ticker].get("peak_price", spx_now)
                    if peak > 0 and spx_now > 0:
                        drawdown = (peak - spx_now) / peak
                        stop_threshold = 0.05
                        if drawdown >= (stop_threshold - self.STOP_APPROACH_BUFFER):
                            events.append({
                                "type": "STOP_APPROACH",
                                "severity": "ELEVATED",
                                "detail": f"{ticker} within {self.STOP_APPROACH_BUFFER:.1%} of trailing stop (drawdown: {drawdown:.2%})"
                            })

        return events

    def should_trigger_pipeline(self, events: list) -> tuple:
        """
        Returns (should_run: bool, interval_to_use: str, reason: str)
        """
        if not events:
            return False, None, None

        severities = [e["severity"] for e in events]
        types = [e["type"] for e in events]

        if "CRITICAL" in severities:
            return True, "1h", f"Critical event: {types}"
        if "STOP_APPROACH" in types or "VOLATILITY_SPIKE" in types:
            return True, "1h", f"Defensive trigger: {types}"
        if "ENTRY_FLIP" in types:
            return True, "4h", f"Opportunity: {types}"

        return False, None, None
