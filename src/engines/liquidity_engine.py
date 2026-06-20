import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, Any

class LiquidityEngine:
    def __init__(self, atr_period: int = 14, cluster_tolerance_atr_pct: float = 0.5, history_bars: int = 100):
        self.atr_period = atr_period
        self.cluster_tolerance_atr_pct = cluster_tolerance_atr_pct
        self.history_bars = history_bars

    def compute(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        """
        Builds a heatmap of historical liquidity clusters (swing highs/lows)
        and identifies the nearest pools above/below current price.
        """
        if len(ohlcv) < self.history_bars:
            return {
                "nearest_pool_above": 0.0,
                "nearest_pool_below": 0.0,
                "magnet_target": "NONE",
                "pool_strength_above": 0,
                "pool_strength_below": 0
            }

        # Calculate ATR
        tr = np.maximum(
            ohlcv["High"] - ohlcv["Low"], 
            np.maximum(
                abs(ohlcv["High"] - ohlcv["Close"].shift(1)), 
                abs(ohlcv["Low"] - ohlcv["Close"].shift(1))
            )
        )
        atr = tr.rolling(self.atr_period).mean().iloc[-1]
        
        # We need a fallback if atr is nan
        if np.isnan(atr) or atr <= 0:
            atr = ohlcv["Close"].iloc[-1] * 0.01

        highs = ohlcv["High"].iloc[-self.history_bars:]
        lows = ohlcv["Low"].iloc[-self.history_bars:]
        
        # Simple swing highs/lows
        swing_highs = []
        swing_lows = []
        for i in range(2, len(highs)-2):
            if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
               highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
                swing_highs.append(highs.iloc[i])
                
            if lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i-2] and \
               lows.iloc[i] < lows.iloc[i+1] and lows.iloc[i] < lows.iloc[i+2]:
                swing_lows.append(lows.iloc[i])

        # Cluster swings
        tolerance = atr * self.cluster_tolerance_atr_pct
        
        def cluster_swings(swings):
            swings = sorted(swings)
            clusters = []
            if not swings: return clusters
            current_cluster = [swings[0]]
            for s in swings[1:]:
                if abs(s - np.mean(current_cluster)) <= tolerance:
                    current_cluster.append(s)
                else:
                    clusters.append({
                        "price": np.mean(current_cluster), 
                        "strength": len(current_cluster)
                    })
                    current_cluster = [s]
            clusters.append({
                "price": np.mean(current_cluster), 
                "strength": len(current_cluster)
            })
            return clusters

        cluster_highs = cluster_swings(swing_highs)
        cluster_lows = cluster_swings(swing_lows)
        
        current_price = float(ohlcv["Close"].iloc[-1])
        
        # Find nearest above
        above = [c for c in cluster_highs if c["price"] > current_price]
        above.sort(key=lambda x: x["price"])
        nearest_above = above[0] if above else {"price": 0.0, "strength": 0}
        
        # Find nearest below
        below = [c for c in cluster_lows if c["price"] < current_price]
        below.sort(key=lambda x: -x["price"])
        nearest_below = below[0] if below else {"price": 0.0, "strength": 0}
        
        # Determine Magnet
        # The pool with highest strength within 2 ATRs is the magnet
        magnet_target = "NONE"
        if nearest_above["strength"] > nearest_below["strength"] and (nearest_above["price"] - current_price) < 2*atr:
            magnet_target = "UP"
        elif nearest_below["strength"] > nearest_above["strength"] and (current_price - nearest_below["price"]) < 2*atr:
            magnet_target = "DOWN"

        return {
            "nearest_pool_above": float(nearest_above["price"]),
            "nearest_pool_below": float(nearest_below["price"]),
            "magnet_target": magnet_target,
            "pool_strength_above": nearest_above["strength"],
            "pool_strength_below": nearest_below["strength"]
        }
