import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class SMCState:
    bos_direction: int          # +1 bullish BOS, -1 bearish BOS, 0 none
    choch_detected: bool        # True if structure flip this bar
    active_ob_bullish: float    # Price of nearest bullish order block
    active_ob_bearish: float    # Price of nearest bearish order block
    fvg_bullish_active: bool    # Unmitigated bullish FVG above current price
    fvg_bearish_active: bool    # Unmitigated bearish FVG below current price
    liquidity_swept_low: bool   # Sweep of swing low in last N bars
    liquidity_swept_high: bool  # Sweep of swing high in last N bars
    premium_discount: str       # "PREMIUM" / "DISCOUNT" / "EQUILIBRIUM" vs range
    smc_bias: int               # Net directional bias: +1 / -1 / 0

class SMCEngine:
    def __init__(self, swing_period: int = 10, fvg_min_pct: float = 0.001):
        self.swing_period = swing_period
        self.fvg_min_pct = fvg_min_pct

    def _find_swings(self, high: pd.Series, low: pd.Series, n: int):
        swing_highs = []
        swing_lows = []
        # Need to ensure enough data
        if len(high) < 2*n + 1:
            return swing_highs, swing_lows
            
        for i in range(n, len(high) - n):
            if all(high.iloc[i] >= high.iloc[i-n:i]) and all(high.iloc[i] >= high.iloc[i+1:i+n+1]):
                swing_highs.append((i, float(high.iloc[i])))
            if all(low.iloc[i] <= low.iloc[i-n:i]) and all(low.iloc[i] <= low.iloc[i+1:i+n+1]):
                swing_lows.append((i, float(low.iloc[i])))
        return swing_highs, swing_lows

    def _detect_bos_choch(self, close, swing_highs, swing_lows):
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0, False
        last_close = float(close.iloc[-1])
        prev_high = swing_highs[-2][1]
        prev_low = swing_lows[-2][1]
        last_high = swing_highs[-1][1]
        last_low = swing_lows[-1][1]

        # BOS: continuation break
        if last_close > prev_high and last_high > prev_high:
            return +1, False   # Bullish BOS
        if last_close < prev_low and last_low < prev_low:
            return -1, False   # Bearish BOS

        # CHoCH: counter-structure break
        if last_close > last_high and last_high < prev_high:
            return +1, True    # Bullish CHoCH
        if last_close < last_low and last_low > prev_low:
            return -1, True    # Bearish CHoCH

        return 0, False

    def _detect_fvg(self, ohlcv: pd.DataFrame):
        bullish_fvg = False
        bearish_fvg = False
        if len(ohlcv) < 3:
            return bullish_fvg, bearish_fvg
        c1 = ohlcv.iloc[-3]
        c3 = ohlcv.iloc[-1]
        if c1["Close"] == 0:
            return bullish_fvg, bearish_fvg
            
        bull_gap_size = (c3["Low"] - c1["High"]) / c1["Close"]
        bear_gap_size = (c1["Low"] - c3["High"]) / c1["Close"]
        
        if c3["Low"] > c1["High"] and bull_gap_size >= self.fvg_min_pct:
            bullish_fvg = True
        if c3["High"] < c1["Low"] and bear_gap_size >= self.fvg_min_pct:
            bearish_fvg = True
        return bullish_fvg, bearish_fvg

    def _detect_liquidity_sweep(self, high, low, swing_highs, swing_lows, lookback=5):
        swept_low = False
        swept_high = False
        if len(high) < lookback:
            return swept_low, swept_high
            
        recent_high = high.iloc[-lookback:]
        recent_low = low.iloc[-lookback:]
        
        for _, sh in swing_highs[-3:]:
            if recent_high.max() > sh and recent_high.iloc[-1] < sh:
                swept_high = True
        for _, sl in swing_lows[-3:]:
            if recent_low.min() < sl and recent_low.iloc[-1] > sl:
                swept_low = True
        return swept_low, swept_high

    def compute(self, ohlcv: pd.DataFrame) -> SMCState:
        if len(ohlcv) < self.swing_period * 2 + 1:
            return SMCState(0, False, 0.0, 0.0, False, False, False, False, "EQUILIBRIUM", 0)

        high = ohlcv["High"]
        low = ohlcv["Low"]
        close = ohlcv["Close"]

        swing_highs, swing_lows = self._find_swings(high, low, self.swing_period)
        bos_dir, choch = self._detect_bos_choch(close, swing_highs, swing_lows)
        fvg_bull, fvg_bear = self._detect_fvg(ohlcv)
        swept_low, swept_high = self._detect_liquidity_sweep(high, low, swing_highs, swing_lows)

        # Nearest order blocks
        ob_bull = swing_lows[-1][1] if swing_lows else 0.0
        ob_bear = swing_highs[-1][1] if swing_highs else 0.0

        # Premium / Discount relative to recent range
        if swing_highs and swing_lows:
            range_high = swing_highs[-1][1]
            range_low = swing_lows[-1][1]
            mid = (range_high + range_low) / 2
            price = float(close.iloc[-1])
            if price > mid * 1.01:
                prem_disc = "PREMIUM"
            elif price < mid * 0.99:
                prem_disc = "DISCOUNT"
            else:
                prem_disc = "EQUILIBRIUM"
        else:
            prem_disc = "EQUILIBRIUM"

        # Net SMC bias
        bias_score = 0
        bias_score += bos_dir
        if swept_low and bos_dir >= 0:
            bias_score += 1   # liquidity grab below = accumulation
        if swept_high and bos_dir <= 0:
            bias_score -= 1   # liquidity grab above = distribution
        if fvg_bull and prem_disc == "DISCOUNT":
            bias_score += 1
        if fvg_bear and prem_disc == "PREMIUM":
            bias_score -= 1
            
        smc_bias = 1 if bias_score >= 2 else -1 if bias_score <= -2 else 0

        return SMCState(
            bos_direction=bos_dir,
            choch_detected=choch,
            active_ob_bullish=ob_bull,
            active_ob_bearish=ob_bear,
            fvg_bullish_active=fvg_bull,
            fvg_bearish_active=fvg_bear,
            liquidity_swept_low=swept_low,
            liquidity_swept_high=swept_high,
            premium_discount=prem_disc,
            smc_bias=smc_bias
        )
