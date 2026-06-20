import pandas as pd
import numpy as np
from datetime import datetime

class SessionEngine:
    def compute_orb_signal(self, ohlcv_1h: pd.DataFrame) -> dict:
        """
        Identify the ORB from the first 1H bar after session open.
        Returns breakout direction and strength.
        """
        if len(ohlcv_1h) < 2:
            return {"orb_signal": 0, "orb_strength": 0.0, "orb_high": 0.0, "orb_low": 0.0}
            
        today = ohlcv_1h.index[-1].date()
        session_bars = ohlcv_1h[ohlcv_1h.index.date == today]
        if len(session_bars) < 2:
            return {"orb_signal": 0, "orb_strength": 0.0, "orb_high": 0.0, "orb_low": 0.0}

        orb_bar = session_bars.iloc[0]
        orb_high = float(orb_bar["High"])
        orb_low = float(orb_bar["Low"])
        orb_range = orb_high - orb_low

        current = session_bars.iloc[-1]
        current_close = float(current["Close"])

        # Breakout with range normalization
        if current_close > orb_high:
            strength = (current_close - orb_high) / orb_range if orb_range > 0 else 0
            return {"orb_signal": 1, "orb_strength": min(strength, 3.0),
                    "orb_high": orb_high, "orb_low": orb_low}
        elif current_close < orb_low:
            strength = (orb_low - current_close) / orb_range if orb_range > 0 else 0
            return {"orb_signal": -1, "orb_strength": min(strength, 3.0),
                    "orb_high": orb_high, "orb_low": orb_low}
        return {"orb_signal": 0, "orb_strength": 0.0, "orb_high": orb_high, "orb_low": orb_low}

    def compute_td_sequential(self, close: pd.Series) -> pd.Series:
        """
        Returns TD Sequential count. Positive = setup (closes > close[-4]).
        At 9 = exhaustion signal. Negative = opposite direction.
        """
        count = pd.Series(0, index=close.index)
        if len(close) < 5:
            return count
            
        direction = 0
        c = 0
        for i in range(4, len(close)):
            if close.iloc[i] > close.iloc[i-4]:
                if direction != 1:
                    c = 0
                    direction = 1
                c += 1
            elif close.iloc[i] < close.iloc[i-4]:
                if direction != -1:
                    c = 0
                    direction = -1
                c -= 1
            else:
                c = 0
                direction = 0
            count.iloc[i] = min(max(c, -13), 13)   # cap at 13
        return count

    def td9_exhaustion_signal(self, close: pd.Series) -> dict:
        td = self.compute_td_sequential(close)
        if len(td) == 0:
            return {"td9_exhaustion": False, "td9_direction": 0, "td9_count": 0, "td9_perfected": False}
            
        last = int(td.iloc[-1])
        # At 9 or 13: high probability reversal
        if abs(last) == 9 or abs(last) == 13:
            return {"td9_exhaustion": True, "td9_direction": -np.sign(last),
                    "td9_count": last, "td9_perfected": abs(last) == 13}
        return {"td9_exhaustion": False, "td9_direction": np.sign(last),
                "td9_count": last, "td9_perfected": False}

    def compute_session_state(self, ohlcv_1h: pd.DataFrame, utc_now: datetime) -> dict:
        if len(ohlcv_1h) == 0:
            return {
                "current_session": "UNKNOWN",
                "session_bias": "AVOID",
                "asia_high": 0.0,
                "asia_low": 0.0,
                "london_swept_asia_high": False,
                "london_swept_asia_low": False,
                "favorable_for_entry": False
            }
            
        hour = utc_now.hour

        # Define session windows
        asia_mask    = (ohlcv_1h.index.hour >= 0)  & (ohlcv_1h.index.hour < 8)
        london_mask  = (ohlcv_1h.index.hour >= 7)  & (ohlcv_1h.index.hour < 12)

        today = ohlcv_1h.index[-1].date()
        asia_bars   = ohlcv_1h[(ohlcv_1h.index.date == today) & asia_mask]
        london_bars = ohlcv_1h[(ohlcv_1h.index.date == today) & london_mask]

        asia_high = float(asia_bars["High"].max()) if len(asia_bars) else 0.0
        asia_low  = float(asia_bars["Low"].min())  if len(asia_bars) else 0.0

        current_price = float(ohlcv_1h["Close"].iloc[-1])

        # Did London sweep the Asian range (liquidity grab)?
        london_swept_asia_high = bool(len(london_bars) and london_bars["High"].max() > asia_high and
                                       london_bars["Close"].iloc[-1] < asia_high) if asia_high > 0 else False
        london_swept_asia_low  = bool(len(london_bars) and london_bars["Low"].min() < asia_low and
                                       london_bars["Close"].iloc[-1] > asia_low) if asia_low > 0 else False

        # Current session
        if 0 <= hour < 7:
            current_session = "ASIA"
            session_bias = "RANGE"
        elif 7 <= hour < 12:
            current_session = "LONDON"
            session_bias = "TREND_FORMING"
        elif 12 <= hour < 13:
            current_session = "OVERLAP"
            session_bias = "HIGH_VOLATILITY"
        elif 13 <= hour < 21:
            current_session = "NEW_YORK"
            session_bias = "TREND_CONFIRMING"
        else:
            current_session = "OFF_HOURS"
            session_bias = "AVOID"

        return {
            "current_session": current_session,
            "session_bias": session_bias,
            "asia_high": asia_high,
            "asia_low": asia_low,
            "london_swept_asia_high": london_swept_asia_high,
            "london_swept_asia_low": london_swept_asia_low,
            "favorable_for_entry": current_session in ("LONDON", "NEW_YORK")
        }
