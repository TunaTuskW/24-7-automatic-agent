import pandas as pd
import numpy as np
from datetime import datetime, timezone
import yfinance as yf
from src.observability.logger import get_logger

logger = get_logger("entry-engine")

class EntryEngine:
    """
    Computes a 1H entry quality score (0.0 to 1.0) and a directional bias
    to gate 4H and 1D Kelly sizing.
    """

    def _compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss.replace(0, 0.0001)
        return 100 - (100 / (1 + rs))

    def _compute_macd(self, series: pd.Series) -> tuple:
        exp1 = series.ewm(span=12, adjust=False).mean()
        exp2 = series.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return macd, signal, hist

    def score_entry(
        self,
        spx_close_1h: pd.Series,
        spx_vol_1h: pd.Series,
        spx_high_1h: pd.Series,
        spx_low_1h: pd.Series,
        vix_1h: pd.Series,
        dominant_regime: str,
        kalman_dominant_state: str,
        smc_bias: int = 0,
        trend_state: str = "UNKNOWN",
        trend_conviction: float = 0.5,
        vix9d_1h: pd.Series = None
    ) -> dict:
        
        components = {
            "volume_confirmation": 0.0,
            "rsi_context": 0.0,
            "macd_momentum": 0.0,
            "vix_term_structure": 0.0,
            "price_vs_ema20": 0.0,
            "pwh_pwl_proximity": 0.0,
            "signal_conflict": 0.0
        }
        
        if len(spx_close_1h) < 26:
            logger.warning("Insufficient 1H data for entry scoring. Returning 0.5 FLAT.")
            return {"entry_score": 0.5, "entry_bias": "FLAT", "components": components}

        is_long_bias = False
        try:
            # Current values
            close_now = float(spx_close_1h.iloc[-1])
            high_now = float(spx_high_1h.iloc[-1])
            low_now = float(spx_low_1h.iloc[-1])
            vol_now = float(spx_vol_1h.iloc[-1])
            
            # Determine base directional bias based on SMC + Trend
            if smc_bias > 0 and trend_state == "UPTREND":
                is_long_bias = True
            elif smc_bias < 0 and trend_state == "DOWNTREND":
                is_long_bias = False
            elif smc_bias == 0 and trend_state in ("TRANSITIONAL", "FLAT"):
                is_long_bias = spx_close_1h.iloc[-1] > spx_close_1h.iloc[-5]
            else:
                is_long_bias = spx_close_1h.iloc[-1] > spx_close_1h.iloc[-5]
                components["signal_conflict"] = -0.20
            
            if kalman_dominant_state == "risk_off":
                is_long_bias = False

            # 1. Volume confirmation (0.25)
            vol_mean = spx_vol_1h.rolling(20).mean().iloc[-2]
            bar_range = high_now - low_now
            if bar_range > 0:
                close_pos = (close_now - low_now) / bar_range
                if is_long_bias:
                    if vol_now > vol_mean and close_pos >= 0.5:
                        components["volume_confirmation"] = 1.0
                else:
                    if vol_now > vol_mean and close_pos <= 0.5:
                        components["volume_confirmation"] = 1.0
            
            # 2. RSI context (0.20)
            rsi = self._compute_rsi(spx_close_1h, 14)
            rsi_now = float(rsi.iloc[-1])
            if is_long_bias:
                if 40 <= rsi_now <= 68:
                    components["rsi_context"] = 1.0
            else:
                if 32 <= rsi_now <= 60:
                    components["rsi_context"] = 1.0

            # 3. MACD momentum (0.20)
            _, _, hist = self._compute_macd(spx_close_1h)
            h0, h1, h2 = float(hist.iloc[-1]), float(hist.iloc[-2]), float(hist.iloc[-3])
            if is_long_bias:
                if h0 > 0 and h0 > h1 and h1 > h2:
                    components["macd_momentum"] = 1.0
            else:
                if h0 < 0 and h0 < h1 and h1 < h2:
                    components["macd_momentum"] = 1.0

            # 4. VIX Term Structure (0.15)
            try:
                if vix9d_1h is not None and not vix9d_1h.empty:
                    vix9d_now = float(vix9d_1h.iloc[-1])
                    vix_now = float(vix_1h.iloc[-1]) if len(vix_1h) > 0 else vix9d_now + 1.0
                    
                    if is_long_bias and vix9d_now < vix_now:
                        components["vix_term_structure"] = 1.0
                    elif not is_long_bias and vix9d_now > vix_now:
                        components["vix_term_structure"] = 1.0
                else:
                    # Fallback if VIX9D fails
                    if len(vix_1h) > 0:
                        if is_long_bias and float(vix_1h.iloc[-1]) < 20:
                            components["vix_term_structure"] = 0.5
                        elif not is_long_bias and float(vix_1h.iloc[-1]) > 20:
                            components["vix_term_structure"] = 1.0
            except Exception:
                pass

            # 5. Price vs EMA-20 (0.10)
            ema20 = spx_close_1h.ewm(span=20, adjust=False).mean()
            ema20_now = float(ema20.iloc[-1])
            if is_long_bias and close_now > ema20_now:
                components["price_vs_ema20"] = 1.0
            elif not is_long_bias and close_now < ema20_now:
                components["price_vs_ema20"] = 1.0

            # 6. PWH/PWL proximity (0.10)
            recent_high = float(spx_high_1h.iloc[-35:].max())
            recent_low = float(spx_low_1h.iloc[-35:].min())
            if is_long_bias:
                dist_to_high = (recent_high - close_now) / close_now
                if dist_to_high > 0.003:
                    components["pwh_pwl_proximity"] = 1.0
            else:
                dist_to_low = (close_now - recent_low) / close_now
                if dist_to_low > 0.003:
                    components["pwh_pwl_proximity"] = 1.0

        except Exception as e:
            logger.error(f"EntryEngine scoring failed: {e}")
            return {"entry_score": 0.5, "entry_bias": "FLAT", "components": components}

        score = (
            components["volume_confirmation"] * 0.25 +
            components["rsi_context"] * 0.20 +
            components["macd_momentum"] * 0.20 +
            components["vix_term_structure"] * 0.15 +
            components["price_vs_ema20"] * 0.10 +
            components["pwh_pwl_proximity"] * 0.10 +
            components["signal_conflict"]
        )
        score = max(0.0, min(1.0, score))
        
        bias = "LONG" if is_long_bias else "SHORT"
        if kalman_dominant_state == "risk_off":
            bias = "SHORT"
            
        return {
            "entry_score": round(score, 3),
            "entry_bias": bias,
            "components": components
        }
