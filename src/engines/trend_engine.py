import numpy as np
import pandas as pd

def compute_linreg_candles(ohlcv: pd.DataFrame, period: int = 11) -> pd.DataFrame:
    """Replace OHLC with linear regression estimates to remove noise."""
    lr = pd.DataFrame(np.nan, index=ohlcv.index, columns=ohlcv.columns)
    if len(ohlcv) < period:
        return lr
        
    for col in ["Open", "High", "Low", "Close"]:
        # Use simple moving average as a fallback if polyfit is too slow, but sticking to polyfit for now
        x = np.arange(period)
        
        # We need to apply a rolling window and compute the endpoint of the regression line
        def apply_linreg(window):
            if np.isnan(window).any(): return np.nan
            slope, intercept = np.polyfit(x, window, 1)
            return slope * (period - 1) + intercept
            
        lr[col] = ohlcv[col].rolling(period).apply(apply_linreg, raw=True)
        
    return lr

def compute_ut_bot_signal(close: pd.Series, atr: pd.Series, key_value: float = 1.5) -> pd.Series:
    """
    Compute ATR trailing stop and derive directional signal.
    Returns Series: +1 (bull), -1 (bear), 0 (flat)
    """
    n = len(close)
    stop = pd.Series(0.0, index=close.index)
    direction = pd.Series(0, index=close.index)
    
    if n == 0:
        return direction

    # Initial stop
    stop.iloc[0] = close.iloc[0] - key_value * atr.iloc[0]

    for i in range(1, n):
        prev_stop = stop.iloc[i-1]
        c = close.iloc[i]
        a = atr.iloc[i]

        new_stop = c - key_value * a if c > prev_stop else c + key_value * a
        
        # Trailing logic: never move against the current trend
        if close.iloc[i-1] > prev_stop and c > prev_stop:
            new_stop = max(new_stop, prev_stop)
        elif close.iloc[i-1] < prev_stop and c < prev_stop:
            new_stop = min(new_stop, prev_stop)
            
        stop.iloc[i] = new_stop

    # Signal: price > stop -> bull, price < stop -> bear
    direction = np.where(close > stop, 1, -1)
    return pd.Series(direction, index=close.index)

class TrendEngine:
    def score(self, ohlcv: pd.DataFrame, atr_period: int = 14, fast_kv: float = 1.5, slow_kv: float = 3.0, linreg_period: int = 11) -> dict:
        if len(ohlcv) < max(atr_period, linreg_period) + 1:
            return {
                "trend_state": "UNKNOWN",
                "trend_conviction": 0.0,
                "fast_signal": 0,
                "slow_signal": 0,
                "atr_stop_fast": 0.0
            }
            
        lr = compute_linreg_candles(ohlcv, period=linreg_period)
        close = lr["Close"]
        
        if close.dropna().empty:
            return {
                "trend_state": "FLAT",
                "trend_conviction": 0.50,
                "fast_signal": 0,
                "slow_signal": 0,
                "atr_stop_fast": 0.0,
            }
        
        # Approximate ATR using TR
        tr = np.maximum(
            ohlcv["High"] - ohlcv["Low"], 
            np.maximum(
                abs(ohlcv["High"] - ohlcv["Close"].shift(1)), 
                abs(ohlcv["Low"] - ohlcv["Close"].shift(1))
            )
        )
        atr = tr.rolling(atr_period, min_periods=1).mean()

        fast_signal = compute_ut_bot_signal(close, atr, key_value=fast_kv)
        slow_signal = compute_ut_bot_signal(close, atr, key_value=slow_kv)

        # Dual confirmation: both agree = high conviction
        last_fast = int(fast_signal.iloc[-1])
        last_slow = int(slow_signal.iloc[-1])

        if last_fast == 1 and last_slow == 1:
            trend_state = "UPTREND"
            trend_conviction = 0.85
        elif last_fast == -1 and last_slow == -1:
            trend_state = "DOWNTREND"
            trend_conviction = 0.85
        elif last_fast != last_slow:
            trend_state = "TRANSITIONAL"
            trend_conviction = 0.40
        else:
            trend_state = "FLAT"
            trend_conviction = 0.50

        # Calculate fast stop value natively for output
        c = float(close.iloc[-1])
        a = float(atr.iloc[-1])
        # Just rough approx of the stop value for telemetry:
        stop_val = c - fast_kv * a if last_fast == 1 else c + fast_kv * a

        return {
            "trend_state": trend_state,
            "trend_conviction": trend_conviction,
            "fast_signal": last_fast,
            "slow_signal": last_slow,
            "atr_stop_fast": float(stop_val),
        }
