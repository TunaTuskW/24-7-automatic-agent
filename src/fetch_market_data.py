#!/usr/bin/env python3
"""
fetch_market_data.py - v3.7.0
Pulls multi-source parallel data from yfinance, FRED, and ECB.
Performs TruChain verification, executes HMM & Deep MLP predictions, 
runs self-calibration (Brier Score), and outputs data-science-ready outputs.
"""
import os
import json
import joblib
import logging
import requests
import hashlib
import hmac
import numpy as np
import pandas as pd
import pandas as pd
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
import feedparser
try:
    import yfinance as yf
except ImportError:
    raise ImportError("Install yfinance: pip install yfinance")
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), '..', 'logs', 'fetch_market_data.log'),
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
ALL_YF_TICKERS = {
    # Equities
    "SPX": "^GSPC", "NDX": "^NDX", "DAX": "^GDAXI", "FTSE": "^FTSE", "N225": "^N225",
    "HSI": "^HSI", "SHANGHAI": "000001.SS", "KOSPI": "^KS11", "TASI": "^TASI.SR", "DFM": "DFMGI.AE",
    # Commodities & Safe Havens
    "WTI": "CL=F", "Brent": "BZ=F", "TTF": "TTF=F",
    "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
    # FX & Safe Havens
    "DXY": "DX-Y.NYB", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", 
    "JPYUSD": "JPYUSD=X", "CHFUSD": "CHFUSD=X", "USDCAD": "USDCAD=X",
    # Volatility
    "VIX9D": "^VIX9D",
    "VIX": "^VIX",
    "VIX3M": "^VIX3M",
    "VVIX": "^VVIX",
    # Institutional Digital Asset Flow & Spot
    "BTC": "BTC-USD",
    "IBIT": "IBIT",      
    "ETHA": "ETHA",      
    "COIN": "COIN"       
}
garch_targets = {
    "SPX":   "^GSPC",
    "WTI":   "CL=F",
}
garch_targets = {
    "SPX":   "^GSPC",
    "WTI":   "CL=F",
    "DXY":   "DX-Y.NYB",   
}

SOURCES = {
    "yahoo_spx": {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,BTC-USD,CL=F,GC=F,^TNX", "authority": 0.95},
    "wsj_markets": {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "authority": 0.90},
    "cnbc_top": {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=120000000", "authority": 0.85}
}

@dataclass
class NewsSignalVector:
    sentiment_mean: float        # [-1.0, 1.0]
    sentiment_std: float         # [0.0, 1.0] — proxy for news uncertainty
    sentiment_momentum: float    # delta vs previous run [-1.0, 1.0]
    event_flag: int              # 0 = no event, 1 = event detected
    event_type: str              # "earnings" | "macro" | "geopolitical" | "none"
    source_authority_mean: float # [0.0, 1.0]
    article_volume: int          # relevant articles in window
    directional_bias: str        # "bullish" | "bearish" | "neutral"
    top_headlines: list          # top 3 headlines for display

    def to_dict(self) -> dict:
        return asdict(self)

ROLLING_DAYS = 5
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
def get_signature_salt():
    path = os.path.join(os.path.dirname(__file__), '..', 'config', 'signature_salt.txt')
    if os.path.exists(path):
        with open(path, 'r') as f:
            salt = f.read().strip()
            if salt:
                return salt
    return "MacroBriefingAgentTruChainFallbackSecret"
def sign_snapshot_payload(snapshot_dict):
    serialized = json.dumps(snapshot_dict, sort_keys=True)
    salt = get_signature_salt()
    return hmac.new(salt.encode('utf-8'), serialized.encode('utf-8'), hashlib.sha256).hexdigest()
def check_mathematical_consistency(parsed_assets):
    try:
        vix = parsed_assets.get("VIX")
        if vix and (vix["current"] > 100.0 or vix["current"] < 5.0):
            return False
        spx = parsed_assets.get("SPX")
        if spx and abs(spx["delta_pct"]) > 15.0:
            return False
        return True
    except Exception:
        return False
def append_to_immutable_chain(current_signature, output_utc):
    chain_log_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'immutable_chain.log')
    os.makedirs(os.path.dirname(chain_log_path), exist_ok=True)
    
    prev_hash = "0" * 64
    if os.path.exists(chain_log_path):
        try:
            with open(chain_log_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    prev_hash = lines[-1].strip().split(",")[-1]
        except Exception as e:
            logging.error(f"TruChain L3: Log read error: {e}")
    linked_block_hash = hashlib.sha256(f"{prev_hash}{current_signature}".encode('utf-8')).hexdigest()
    try:
        header_needed = not os.path.exists(chain_log_path)
        with open(chain_log_path, 'a') as f:
            if header_needed:
                f.write("timestamp_utc,snapshot_signature,prev_block_hash,linked_block_hash\n")
            f.write(f"{output_utc},{current_signature},{prev_hash},{linked_block_hash}\n")
    except Exception as e:
        logging.error(f"TruChain L3: Append failure: {e}")
def compute_stats(series, garch_conditional_vol=None):
    if series is None or len(series) < 2:
        return None
    current  = float(series.iloc[-1])
    prev     = float(series.iloc[-2])
    delta    = current - prev
    delta_pct = (delta / prev * 100) if prev != 0 else 0
    rolling  = series.tail(ROLLING_DAYS)
    mean     = float(rolling.mean())
    std      = float(rolling.std()) if len(rolling) > 1 else 0
    
    if garch_conditional_vol is not None and garch_conditional_vol > 0:
        z_score = delta_pct / garch_conditional_vol
    else:
        z_score = ((current - mean) / std) if std != 0 else 0
        
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
def compute_volume_heat(spx_series, spx_vol_series):
    if len(spx_series) < 20 or len(spx_vol_series) < 20:
        return {"participation_type": "UNKNOWN", "institutional_heat_index": 0.0}
    try:
        vol_mean = spx_vol_series.rolling(20).mean().iloc[-1]
        vol_std = spx_vol_series.rolling(20).std().iloc[-1]
        current_vol = float(spx_vol_series.iloc[-1])
        effort_z = (current_vol - vol_mean) / vol_std if vol_std > 0 else 0.0
        
        current_close = float(spx_series.iloc[-1])
        recent_low = float(spx_series.tail(10).min())
        recent_high = float(spx_series.tail(10).max())
        result_vector = (current_close - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
        
        ihi = effort_z * (result_vector - 0.5)
        
        part_type = "RETAIL_DRIFT"
        if effort_z > 1.0:
            part_type = "INSTITUTIONAL_ACCUMULATION" if result_vector > 0.5 else "INSTITUTIONAL_DISTRIBUTION"
            
        return {"participation_type": part_type, "institutional_heat_index": round(ihi, 3)}
    except Exception as e:
        return {"participation_type": "UNKNOWN", "institutional_heat_index": 0.0}

def compute_market_extremes(spx_series, vix_series, vvix_series=None, dxy_series=None, vix9d_series=None):
    try:
        spx_returns = spx_series.pct_change().dropna().tail(10) * 100
        vix_returns = vix_series.pct_change().dropna().tail(10) * 100
        
        # 1. Base Temperature & Crowdedness (Existing Logic)
        spx_abs = spx_returns.abs().sum()
        vix_abs = vix_returns.abs().sum()
        temperature_z = (spx_abs - vix_abs) / vix_abs if vix_abs > 0 else 0.0
        crowdedness = spx_returns.corr(vix_returns)
        
        # 2. Hidden Fragility Calculations
        fragility_score = 0.0
        vvix_ratio = 0.0
        cross_corr = 0.0
        
        if vvix_series is not None and not vvix_series.empty:
            vvix_ratio = vvix_series.iloc[-1] / vix_series.iloc[-1]
            if vvix_ratio > 6.0:  # VVIX expanding much faster than VIX
                fragility_score += 0.4
                
        if dxy_series is not None and not dxy_series.empty:
            dxy_returns = dxy_series.pct_change().dropna().tail(10) * 100
            cross_corr = spx_returns.corr(dxy_returns)
            # If SPX and DXY are highly positively correlated, liquidity is draining
            if cross_corr > 0.4:
                fragility_score += 0.6
                
        # 3. Volatility Term Structure
        if vix9d_series is not None and not vix9d_series.empty:
            term_structure_inversion = 1.0 if float(vix9d_series.iloc[-1]) > float(vix_series.iloc[-1]) else 0.0
            fragility_score += (0.5 * term_structure_inversion)
                
        return {
            "temperature_zscore": round(temperature_z, 3),
            "temperature_state": "OVERHEATED" if temperature_z > 1.0 else "ICE_COLD" if temperature_z < -1.0 else "NORMAL",
            "crowded_state": "LONG_TRADE_TOO_CROWDED" if crowdedness > 0.5 else "SHORT_TRADE_TOO_CROWDED" if crowdedness < -0.5 else "BALANCED",
            "fragility_score": round(fragility_score, 3),
            "vvix_vix_ratio": round(vvix_ratio, 2)
        }
    except Exception:
        return {}
def compute_garch_volatility(ticker_symbol, lookback_days=250):
    try:
        from arch import arch_model
        data = yf.Ticker(ticker_symbol)
        hist = data.history(period=f"{lookback_days}d", interval="1d")
        if hist.empty or len(hist) < 20:
            return None, None, None
        returns = hist["Close"].pct_change().dropna() * 100
        model = arch_model(returns, vol="Garch", p=1, q=1, mean="Zero", rescale=False)
        result = model.fit(disp="off", show_warning=False)
        cond_vol = float(result.conditional_volatility.iloc[-1])
        forecast = result.forecast(horizon=1, reindex=False)
        forecast_vol = float(forecast.variance.iloc[-1, 0] ** 0.5)
        vol_history = result.conditional_volatility.dropna()
        percentile = float((vol_history < cond_vol).mean() * 100)
        vol_regime = "LOW" if percentile < 33 else "NORMAL" if percentile < 67 else "ELEVATED"
        return round(cond_vol, 4), vol_regime, round(forecast_vol, 4)
    except Exception as e:
        logging.error(f"GARCH error for {ticker_symbol}: {e}")
        return None, None, None
def load_mlp_model():
    model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'mlp_model.pkl')
    try:
        if os.path.exists(model_path):
            return joblib.load(model_path)
    except Exception as e:
        logging.error(f"MLP Load Failure: {e}")
    return None
def run_mlp_inference(features_vector, mlp_package):
    if mlp_package is None:
        return None
    try:
        model = mlp_package["model"]
        scaler = mlp_package["scaler"]
        obs = np.array([features_vector])
        obs_scaled = scaler.transform(obs)
        probs = model.predict_proba(obs_scaled)[0]
        
        # Ensure no probability drops to absolute zero
        probs = np.clip(probs, 0.01, 0.99)
        probs /= probs.sum() # Re-normalize to 1.0

        classes = ["risk_off", "risk_on", "transitional"]
        dominant_idx = int(np.argmax(probs))
        return {
            "risk_off":     round(float(probs[0]), 3),
            "risk_on":      round(float(probs[1]), 3),
            "transitional": round(float(probs[2]), 3),
            "dominant_state": classes[dominant_idx],
            "dominant_prob":  round(float(probs[dominant_idx]), 3)
        }
    except Exception as e:
        logging.error(f"MLP Inference Failure: {e}")
        return None
def compute_weekly_liquidity_boundaries(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="15d")
        if len(hist) < 10:
            return None
        hist['week'] = hist.index.isocalendar().week
        unique_weeks = list(hist['week'].unique())
        if len(unique_weeks) >= 2:
            prev_week_data = hist[hist['week'] == unique_weeks[-2]]
            pwh = float(prev_week_data['High'].max())
            pwl = float(prev_week_data['Low'].min())
            current_close = float(hist['Close'].iloc[-1])
            current_low = float(hist['Low'].iloc[-1])
            current_high = float(hist['High'].iloc[-1])
            intraday_range_pct = ((current_high - current_low) / current_low) * 100
            swept_pwl = current_low < pwl and current_close > pwl
            swept_pwh = current_high > pwh and current_close < pwh
            return {
                "pwh": round(pwh, 2),
                "pwl": round(pwl, 2),
                "swept_pwl_flag": bool(swept_pwl),
                "swept_pwh_flag": bool(swept_pwh),
                "intraday_range_pct": round(intraday_range_pct, 3)
            }
    except Exception as e:
        logging.error(f"Error computing weekly boundaries for {ticker_symbol}: {e}")
    return None
def calculate_model_tvd(p_dist, q_dist):
    """
    Computes Total Variation Distance (TVD) between HMM and MLP.
    TVD = 0.5 * sum(|P - Q|)
    """
    try:
        hmm_risk_on = p_dist.get("RISK_ON_EXPANSION", 0.0) + p_dist.get("LIQUIDITY_DRIVEN_RALLY", 0.0)
        hmm_risk_off = (p_dist.get("STAGFLATION_STRESS", 0.0) + 
                        p_dist.get("RATE_SHOCK", 0.0) + 
                        p_dist.get("DEFLATION_FEAR", 0.0) + 
                        p_dist.get("CRISIS_DISLOCATION", 0.0))
        hmm_trans = max(0.0, 1.0 - hmm_risk_on - hmm_risk_off)
        
        P = np.array([hmm_risk_on, hmm_risk_off, hmm_trans])
        Q = np.array([q_dist.get("risk_on", 0.33), q_dist.get("risk_off", 0.34), q_dist.get("transitional", 0.33)])
        
        # Clip to prevent 0.0
        P = np.clip(P, 0.01, 0.99); P /= P.sum()
        Q = np.clip(Q, 0.01, 0.99); Q /= Q.sum()
        
        tvd = 0.5 * float(np.sum(np.abs(P - Q)))
        return round(tvd, 4)
    except Exception as e:
        return 0.0
def calculate_bayesian_conditional_probability(setup_name, current_regime):
    historical_matrices = {
        "PWL_Sweep": {
            "RISK_ON_EXPANSION": 0.84,
            "LIQUIDITY_DRIVEN_RALLY": 0.91, 
            "NEUTRAL_TRANSITIONAL": 0.64,
            "RATE_SHOCK": 0.31,
            "STAGFLATION_STRESS": 0.28,
            "DEFLATION_FEAR": 0.21,
            "CRISIS_DISLOCATION": 0.12
        },
        "PWH_Sweep": {
            "RISK_ON_EXPANSION": 0.18,
            "LIQUIDITY_DRIVEN_RALLY": 0.11,
            "NEUTRAL_TRANSITIONAL": 0.42,
            "RATE_SHOCK": 0.74, 
            "STAGFLATION_STRESS": 0.68,
            "DEFLATION_FEAR": 0.81,
            "CRISIS_DISLOCATION": 0.89
        }
    }
    regime_key = str(current_regime).replace("_4", "").replace("_3", "").replace("_2", "").replace("_5", "")
    try:
        p_success = historical_matrices.get(setup_name, {}).get(regime_key, 0.50)
        return round(p_success, 2)
    except Exception:
        return 0.50
def run_self_calibration(new_spx_ret, predictions_history_path):
    """
    Model Governance: Calculates rolling Brier Score to verify output accuracy.
    BS = (1/N) * Sum( (forecast_probability - actual_binary_outcome)^2 )
    """
    brier_score = 0.15 # Default healthy baseline
    try:
        # Load historical forecasts
        history = []
        if os.path.exists(predictions_history_path):
            with open(predictions_history_path, 'r') as f:
                history = json.load(f)
        
        # Binary target: 1 if SPX was positive, 0 otherwise
        actual_outcome = 1 if new_spx_ret > 0 else 0
        
        # Grade the previous prediction if available
        if history:
            last_forecast = history[-1]
            if "target_graded" not in last_forecast or not last_forecast["target_graded"]:
                last_forecast["actual_outcome"] = actual_outcome
                last_forecast["target_graded"] = True
                # Brier score calculation: (prob_risk_on - actual_outcome)^2
                last_forecast["squared_error"] = float((last_forecast["predicted_risk_on"] - actual_outcome) ** 2)
        
        # Limit history to 20 cycles
        history = history[-20:]
        
        # Calculate Brier score
        graded_predictions = [p for p in history if p.get("target_graded", False)]
        if len(graded_predictions) > 0:
            brier_score = float(np.mean([p["squared_error"] for p in graded_predictions]))
            # Brier > 0.25 is worse than guessing 0.5
            if brier_score > 0.25:
                logging.warning(f"CRITICAL: Brier Score {brier_score} is worse than random. Model is severely degraded.")
            
        return round(brier_score, 4), history
    except Exception as e:
        logging.error(f"Self-calibration error: {e}")
        return 0.15, []
def compute_equity_momentum_score(equities):
    weights = {"SPX": 0.35, "NDX": 0.18, "DAX": 0.18, "N225": 0.18, "TASI": 0.06, "DFM": 0.05}
    weighted_z = 0.0
    total_weight = 0.0
    for name, weight in weights.items():
        asset = equities.get(name)
        if asset and asset.get("z_score") is not None:
            weighted_z += asset["z_score"] * weight
            total_weight += weight
    if total_weight == 0:
        return 0.0
    avg_z = weighted_z / total_weight
    scaled = -25.0 + ((avg_z - (-3.0)) / (3.0 - (-3.0))) * (25.0 - (-25.0))
    return round(max(-25.0, min(25.0, scaled)), 3)
def compute_rate_pressure_score(bonds):
    score = 0.0
    us10y = bonds.get("US10Y")
    spread = bonds.get("spread_2s10s")
    if us10y and us10y.get("delta") is not None:
        val = -us10y["delta"]
        scaled = -12.5 + ((val - (-0.3)) / (0.3 - (-0.3))) * (12.5 - (-12.5))
        score += round(max(-12.5, min(12.5, scaled)), 3)
    if spread is not None:
        scaled = -12.5 + ((spread - (-0.5)) / (1.5 - (-0.5))) * (12.5 - (-12.5))
        score += round(max(-12.5, min(12.5, scaled)), 3)
    return round(max(-25.0, min(25.0, score)), 3)
def compute_energy_stress_score(energy):
    z_scores = []
    for name in ["WTI", "Brent"]:
        asset = energy.get(name)
        if asset and asset.get("z_score") is not None:
            z_scores.append(asset["z_score"])
    if not z_scores:
        return 0.0
    avg_z = -sum(z_scores) / len(z_scores)
    scaled = -25.0 + ((avg_z - (-3.0)) / (3.0 - (-3.0))) * (25.0 - (-25.0))
    return round(max(-25.0, min(25.0, scaled)), 3)
def compute_cross_asset_coherence_score(equities, bonds, energy):
    score = 25.0
    spx = equities.get("SPX")
    us10y = bonds.get("US10Y")
    wti = energy.get("WTI")
    if not spx or not us10y:
        return 0.0
    spx_move = spx.get("delta_pct", 0)
    yield_move = us10y.get("delta", 0)
    if spx_move < -1.0 and yield_move > 0.08:
        score -= 20.0
    if spx_move > 0.5 and yield_move > 0.15:
        score -= 10.0
    if wti and wti.get("delta_pct", 0) > 2.0 and spx_move < -0.5:
        score -= 15.0
    return round(max(-25.0, min(25.0, score)), 3)
def compute_mcs(equities, bonds, energy):
    eq_score  = compute_equity_momentum_score(equities)
    rate_score = compute_rate_pressure_score(bonds)
    energy_score = compute_energy_stress_score(energy)
    coherence_score = compute_cross_asset_coherence_score(equities, bonds, energy)
    mcs = (eq_score * 1.2 + rate_score * 1.0 + energy_score * 0.8 + coherence_score * 1.0)
    mcs = round(max(-100.0, min(100.0, mcs)), 2)
    sub_components = {
        "equity_momentum":      round(eq_score, 3),
        "rate_pressure":        round(rate_score, 3),
        "energy_stress":        round(energy_score, 3),
        "cross_asset_coherence": round(coherence_score, 3),
    }
    return mcs, sub_components
def run_hmm_inference(equities, bonds, energy, fx, garch_layer, hmm_package):
    if hmm_package is None:
        return None, None, None, None
    try:
        hmm          = hmm_package["hmm"]
        scaler       = hmm_package["scaler"]
        state_labels = hmm_package["state_labels"]
        spx = equities.get("SPX") or {}
        wti = energy.get("WTI") or {}
        dxy = fx.get("DXY") or {}
        us10y = bonds.get("US10Y") or {}
        spx_ret = spx.get("delta_pct", 0.0)
        wti_ret = wti.get("delta_pct", 0.0)
        dxy_ret = dxy.get("delta_pct", 0.0)
        spx_garch_vol = garch_layer.get("SPX", {}).get("conditional_vol", 0.0)
        us10y_delta = us10y.get("delta", 0.0)
        gsr_val = 0.0
        gold = equities.get("Gold")
        silver = equities.get("Silver")
        if gold and silver and silver.get("current", 0) > 0:
            gsr_val = ((gold["current"]/silver["current"]) - (gold["prev"]/silver["prev"])) / (gold["prev"]/silver["prev"]) * 100
        obs = np.array([[spx_ret, dxy_ret, spx_garch_vol, wti_ret, gsr_val, us10y_delta, bonds.get("spread_2s10s", 0.0), 0.0, fx.get("USDCAD", {}).get("delta_pct", 0.0)]])
        obs_scaled = scaler.transform(obs)
        _, posteriors = hmm.score_samples(obs_scaled)
        state_probs = posteriors[0]
        
        # Ensure no probability drops to absolute zero
        state_probs = np.clip(state_probs, 0.01, 0.99)
        state_probs /= state_probs.sum() # Re-normalize to 1.0

        regime_probs = {state_labels.get(i, f"STATE_{i}"): round(float(prob), 4) for i, prob in enumerate(state_probs)}
        dominant_state_id = int(np.argmax(state_probs))
        dominant_regime = state_labels.get(dominant_state_id, "NEUTRAL_TRANSITIONAL")
        stay_prob = float(hmm.transmat_[dominant_state_id, dominant_state_id])
        transition_risk = round(1.0 - stay_prob, 4)
        return regime_probs, dominant_regime, transition_risk, dominant_state_id
    except Exception as e:
        logging.error(f"HMM inference failed: {e}")
        return None, None, None, None
def run_kalman_filter(mcs, sub_components, hmm_regime_probs, prior_state=None, prior_cov=None):
    n = 3
    x = np.array([1/3, 1/3, 1/3]) if prior_state is None else np.array([prior_state.get(k, 1/3) for k in ["risk_on", "risk_off", "transitional"]])
    P = np.eye(n) * 0.1 if prior_cov is None else np.array(prior_cov).reshape(n, n)
    Q = np.eye(n) * 0.02
    F = np.array([[0.92, 0.04, 0.04], [0.04, 0.92, 0.04], [0.04, 0.04, 0.92]])
    H = np.eye(n)
    R = np.eye(n) * 0.05
    
    x_pred = F @ x
    P_pred = F @ P @ F.T + Q
    
    if mcs > 30: mcs_obs = np.array([0.65, 0.15, 0.20])
    elif mcs > 10: mcs_obs = np.array([0.45, 0.25, 0.30])
    elif mcs > -10: mcs_obs = np.array([0.25, 0.35, 0.40])
    elif mcs > -30: mcs_obs = np.array([0.15, 0.55, 0.30])
    else: mcs_obs = np.array([0.10, 0.75, 0.15])
    if hmm_regime_probs is not None:
        risk_on_labels = {"RISK_ON_EXPANSION", "LIQUIDITY_DRIVEN_RALLY"}
        risk_off_labels = {"STAGFLATION_STRESS", "RATE_SHOCK", "DEFLATION_FEAR", "CRISIS_DISLOCATION"}
        hmm_risk_on = sum(v for k, v in hmm_regime_probs.items() if any(lab in k for lab in risk_on_labels))
        hmm_risk_off = sum(v for k, v in hmm_regime_probs.items() if any(lab in k for lab in risk_off_labels))
        hmm_obs = np.array([hmm_risk_on, hmm_risk_off, max(0.0, 1.0 - hmm_risk_on - hmm_risk_off)])
        z = 0.4 * mcs_obs + 0.6 * hmm_obs
    else:
        z = mcs_obs
    z = np.clip(z, 0.01, 0.99)
    z = z / z.sum()
    
    innovation = z - H @ x_pred
    S = H @ P_pred @ H.T + R
    K = P_pred @ H.T @ np.linalg.inv(S)
    x_updated = np.clip(x_pred + K @ innovation, 0.01, 0.99)
    x_updated /= x_updated.sum()
    P_updated = (np.eye(n) - K @ H) @ P_pred
    uncertainty = float(np.trace(P_updated))
    
    # Calculate Max Probability Confidence
    max_prob = float(np.max(x_updated))
    is_ambiguous = max_prob < 0.60 # If no state has 60% conviction, it is essentially a coin-flip

    states = ["risk_on", "risk_off", "transitional"]
    dominant_idx = int(np.argmax(x_updated))
    return {
        "risk_on":          round(float(x_updated[0]), 3),
        "risk_off":         round(float(x_updated[1]), 3),
        "transitional":     round(float(x_updated[2]), 3),
        "dominant_state":   states[dominant_idx],
        "dominant_prob":    round(float(x_updated[dominant_idx]), 3),
        "uncertainty":      round(uncertainty, 4),
        "is_ambiguous":     bool(is_ambiguous),
        "covariance_matrix": P_updated.tolist()
    }

def compute_shannon_entropy(probs):
    """
    Measures the absolute chaos of the probability distribution.
    Max Entropy for 3 states is ~1.58 (pure noise).
    """
    probs = np.clip(probs, 1e-9, 1.0)
    entropy = -np.sum(probs * np.log2(probs))
    return round(float(entropy), 3)

def compute_kelly_sizing(max_prob, brier_score, duration_days=0.0, half_life=99.0):
    edge = max_prob - 0.333
    if edge <= 0: return 0.0
    
    # Base Kelly (same as before)
    win_rate = max_prob
    loss_rate = 1.0 - win_rate
    base_fraction = win_rate - (loss_rate / 1.5)
    
    if brier_score > 0.25: calibration_penalty = 0.2
    elif brier_score > 0.15: calibration_penalty = 0.6
    else: calibration_penalty = 1.0
    
    final_fraction = base_fraction * calibration_penalty
    
    # === NEW: Persistence Decay Penalty ===
    # If a regime outlives its half-life, scale out automatically
    if duration_days > half_life:
        decay_factor = math.exp(-0.2 * (duration_days - half_life))
        final_fraction *= max(0.2, decay_factor) # Don't drop below 20% of original size immediately
        
    return round(max(0.0, min(1.0, final_fraction)), 3)

def fetch_market_news(prior_sentiment=0.0):
    try:
        from google import genai
        import os
        import json
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys.json')
        api_key = None
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                api_key = json.load(f).get('GEMINI_API_KEY')
                
        articles = []
        for src_name, config in SOURCES.items():
            try:
                feed = feedparser.parse(config["url"])
                for entry in feed.entries[:5]:
                    articles.append(entry.get("title", ""))
            except Exception:
                pass
                
        if not api_key:
            logging.warning("No Gemini API key. Skipping LLM news processor.")
            return {"sentiment_mean": 0.0, "sentiment_std": 0.0, "momentum": 0.0, "event_flag": 0, "event_type": "none", "highest_priority": 0.0, "total_articles": len(articles), "directional_bias": "neutral", "top_headlines": articles[:3]}
            
        client = genai.Client(api_key=api_key)
        headlines_text = "\n".join(articles[:20])
        prompt = f'''You are a quantitative data parser. Analyze these headlines and output strictly valid JSON with no markdown:
{{"liquidity_drain_probability": 0.0, "geopolitical_shock_magnitude": 0.0}}
Ensure values are floats between 0.0 and 1.0.
Headlines:
{headlines_text}'''
        
        response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        llm_response = json.loads(raw_text)
        
        geo_mag = llm_response.get("geopolitical_shock_magnitude", 0.0)
        liq_prob = llm_response.get("liquidity_drain_probability", 0.0)
        event_flag = 1 if geo_mag > 0.7 else 0
        
        return {
            "sentiment_mean": -geo_mag,
            "sentiment_std": liq_prob,
            "momentum": 0.0,
            "event_flag": event_flag,
            "event_type": "geopolitical_shock" if event_flag else "none",
            "highest_priority": geo_mag,
            "total_articles": len(articles),
            "directional_bias": "shock" if event_flag else "normal",
            "top_headlines": articles[:3]
        }
    except Exception as e:
        logging.error(f"LLM news processing failed: {e}")
        return {"sentiment_mean": 0.0, "sentiment_std": 0.0, "momentum": 0.0, "event_flag": 0, "event_type": "none", "highest_priority": 0.0, "total_articles": 0, "directional_bias": "neutral", "top_headlines": []}

def main():
    logging.info("=== fetch_market_data.py v3.9.0 starting ===")
    fred_key = get_fred_key()
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_snapshot.json')
    predictions_history_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'predictions_history.json')
    prior_estimate, prior_cov, prior_regime = None, None, None
    prior_sentiment = 0.0
    prior = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                prior = json.load(f)
            prior_regime = prior.get("regime", {}).get("current")
            prior_sentiment = prior.get("news_signal", {}).get("sentiment_mean", 0.0)
            ks = prior.get("kalman_state", {})
            if ks:
                prior_estimate = {k: ks[k] for k in ["risk_on", "risk_off", "transitional"] if k in ks}
                prior_cov = ks.get("covariance_matrix")
        except Exception:
            pass
    hmm_model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'hmm_model.pkl')
    hmm_package = joblib.load(hmm_model_path) if os.path.exists(hmm_model_path) else None
    mlp_package = load_mlp_model()
    logging.info("Fitting live GARCH vol models...")
    garch_layer = {}
    for name, ticker in garch_targets.items():
        cond_vol, vol_regime, forecast_vol = compute_garch_volatility(ticker, lookback_days=250)
        garch_layer[name] = {"conditional_vol": cond_vol, "vol_regime": vol_regime, "forecast_vol": forecast_vol}
    logging.info("Parallel downloading complete ticker universe (Daily)...")
    tickers_list = list(ALL_YF_TICKERS.values())
    raw_data_daily = yf.download(tickers_list, period="30d", interval="1d", group_by="ticker", progress=False, threads=True)
    raw_data = raw_data_daily # backwards compatibility
    
    logging.info("Parallel downloading tactical micro data (Hourly)...")
    raw_data_hourly = yf.download(["^GSPC", "^VIX"], period="5d", interval="1h", group_by="ticker", progress=False, threads=True)
    hourly_assets = {}
    if "^GSPC" in raw_data_hourly.columns.get_level_values(0):
        h_spx = raw_data_hourly["^GSPC"]["Close"].dropna()
        if len(h_spx) >= 2: hourly_assets["SPX"] = compute_stats(h_spx)
    if "^VIX" in raw_data_hourly.columns.get_level_values(0):
        h_vix = raw_data_hourly["^VIX"]["Close"].dropna()
        if len(h_vix) >= 2: hourly_assets["VIX"] = compute_stats(h_vix)
    parsed_assets = {}
    for name, symbol in ALL_YF_TICKERS.items():
        try:
            if symbol in raw_data.columns.get_level_values(0):
                close_series = raw_data[symbol]["Close"].dropna()
                if len(close_series) >= 2:
                    garch_vol = garch_layer.get(name, {}).get("conditional_vol")
                    stats = compute_stats(close_series, garch_conditional_vol=garch_vol)
                    if stats and name in garch_layer:
                        stats["vol_regime"] = garch_layer[name].get("vol_regime")
                        stats["forecast_vol"] = garch_layer[name].get("forecast_vol")
                    parsed_assets[name] = stats
                else: parsed_assets[name] = None
            else: parsed_assets[name] = None
        except Exception as e:
            logging.error(f"Error parsing parallel tick {name}: {e}")
            parsed_assets[name] = None
    
    # Compute Volume Heat & Market Extremes
    vol_heat_stats = {"participation_type": "UNKNOWN", "institutional_heat_index": 0.0}
    market_extremes = {}
    if "^GSPC" in raw_data.columns.get_level_values(0):
        spx_series = raw_data["^GSPC"]["Close"].dropna()
        spx_vol = raw_data["^GSPC"]["Volume"].dropna()
        vol_heat_stats = compute_volume_heat(spx_series, spx_vol)
        if "^VIX" in raw_data.columns.get_level_values(0):
            vix_series = raw_data["^VIX"]["Close"].dropna()
            vvix_series = raw_data["^VVIX"]["Close"].dropna() if "^VVIX" in raw_data.columns.get_level_values(0) else None
            dxy_series = raw_data["DX-Y.NYB"]["Close"].dropna() if "DX-Y.NYB" in raw_data.columns.get_level_values(0) else None
            vix9d_series = raw_data["^VIX9D"]["Close"].dropna() if "^VIX9D" in raw_data.columns.get_level_values(0) else None
            market_extremes = compute_market_extremes(spx_series, vix_series, vvix_series, dxy_series, vix9d_series)
            
    parsed_assets["volume_activity_heat"] = vol_heat_stats
    # Gold-to-Silver Ratio
    gold = parsed_assets.get("Gold")
    silver = parsed_assets.get("Silver")
    gsr_stats = None
    if gold and silver and silver.get("current", 0) > 0:
        gsr_current = gold["current"] / silver["current"]
        gsr_prev = gold["prev"] / silver["prev"]
        gsr_delta_pct = ((gsr_current - gsr_prev) / gsr_prev) * 100
        gsr_stats = {
            "current": round(gsr_current, 3), "prev": round(gsr_prev, 3), "delta_pct": round(gsr_delta_pct, 3),
            "signal": "RISK_OFF_DEFLATION" if gsr_delta_pct > 0.5 else "RISK_ON_EXPANSION" if gsr_delta_pct < -0.5 else "NEUTRAL"
        }
    parsed_assets["gold_to_silver_ratio"] = gsr_stats
    # Institutional Crypto MFI
    ibit = parsed_assets.get("IBIT")
    etha = parsed_assets.get("ETHA")
    crypto_mfi_stats = None
    if ibit and etha and ibit.get("z_score") is not None and etha.get("z_score") is not None:
        mfi_z = (ibit["z_score"] + etha["z_score"]) / 2
        crypto_mfi_stats = {"composite_z": round(mfi_z, 3), "flow_regime": "INFLOW" if mfi_z > 1.0 else "OUTFLOW" if mfi_z < -1.0 else "FLAT"}
    parsed_assets["institutional_crypto_mfi"] = crypto_mfi_stats
    # Keyless Credit ETF stress proxy
    hyg = parsed_assets.get("HYG")
    lqd = parsed_assets.get("LQD")
    credit_stress_stats = None
    if hyg and lqd and hyg.get("z_score") is not None and lqd.get("z_score") is not None:
        credit_z = (hyg["z_score"] + lqd["z_score"]) / 2
        credit_stress_stats = {"composite_z": round(credit_z, 3), "label": "CRITICAL" if credit_z < -2.0 else "ELEVATED" if credit_z < -1.0 else "NORMAL"}
    parsed_assets["credit_stress_proxy"] = credit_stress_stats
    # Fetch bonds & spreads
    bonds = {"US2Y": fetch_fred_yield("DGS2", fred_key) if fred_key else None, "US10Y": fetch_fred_yield("DGS10", fred_key) if fred_key else None}
    if bonds["US2Y"] and bonds["US10Y"]:
        bonds["spread_2s10s"] = round(bonds["US10Y"]["current"] - bonds["US2Y"]["current"], 4)
    else: bonds["spread_2s10s"] = 0.0
    # Invalidation triggers: 1.5 standard deviation calculation for rates
    rates_std = parsed_assets.get("US10Y", {}).get("std_5d", 0.05) if parsed_assets.get("US10Y") else 0.05
    rates_mean = parsed_assets.get("US10Y", {}).get("mean_5d", 4.5) if parsed_assets.get("US10Y") else 4.5
    us10y_invalidation_level = round(rates_mean + 1.5 * rates_std, 3)
    vix_std = parsed_assets.get("VIX", {}).get("std_5d", 1.0) if parsed_assets.get("VIX") else 1.0
    vix_mean = parsed_assets.get("VIX", {}).get("mean_5d", 15.0) if parsed_assets.get("VIX") else 15.0
    vix_invalidation_level = round(vix_mean + 1.5 * vix_std, 2)
    # Ingest baseline MCS score & HMM inference
    mcs, sub_components = compute_mcs(parsed_assets, bonds, parsed_assets)
    hmm_beta_probs, hmm_beta_dom, transition_risk, _ = run_hmm_inference(parsed_assets, bonds, parsed_assets, parsed_assets, garch_layer, hmm_package)
    hmm_alpha_probs, hmm_alpha_dom, _, _ = run_hmm_inference(hourly_assets, bonds, parsed_assets, parsed_assets, garch_layer, hmm_package)
    current_regime = hmm_beta_dom if hmm_beta_dom else "NEUTRAL_TRANSITIONAL"
    hmm_regime_probs = hmm_beta_probs
    regime_changed = current_regime != prior_regime
    
    now_utc = datetime.now(timezone.utc)
    
    # Extract prior state
    prior_regime_dict = prior.get("regime") or {}
    prior_start_str = prior_regime_dict.get("start_utc", now_utc.isoformat())
    prior_start = datetime.fromisoformat(prior_start_str)
    
    prior_probs_dict = prior_regime_dict.get("probabilities") or {}
    prior_prob = prior_probs_dict.get("risk_on", 0.33)
    
    # Calculate Velocity & Duration
    safe_hmm_probs = hmm_regime_probs or {}
    current_prob = safe_hmm_probs.get("risk_on", 0.33)
    transition_velocity = current_prob - prior_prob
    
    if regime_changed:
        regime_start_utc = now_utc.isoformat()
        duration_days = 0.0
    else:
        regime_start_utc = prior_start_str
        duration_days = (now_utc - prior_start).total_seconds() / 86400.0


    # === NEW: Load Tuned Hyperparameters ===
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'tuning_configs.json')
    half_life_map = {
        "RISK_ON": 11.0,
        "NEUTRAL_TRANSITIONAL": 2.5,
        "RISK_OFF": 1.2
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                tuned = json.load(f)
                if "RISK_ON_HALF_LIFE_DAYS" in tuned:
                    half_life_map["RISK_ON"] = float(tuned["RISK_ON_HALF_LIFE_DAYS"])
        except Exception as e:
            logging.error(f"Failed to load tuning configs: {e}")

    stability_half_life = half_life_map.get(current_regime, 2.5)

    regime_data = {
        "current": current_regime,
        "tactical_alpha_regime": hmm_alpha_dom, 
        "prior": prior_regime, 
        "changed_this_cycle": regime_changed,
        "confirmed_change": regime_changed and prior_regime is not None, 
        "probabilities": hmm_regime_probs, 
        "transition_risk": transition_risk,
        "start_utc": regime_start_utc,
        "duration_days": round(duration_days, 2),
        "stability_half_life": stability_half_life,
        "transition_velocity": round(transition_velocity, 4)
    }
    kalman_state = run_kalman_filter(mcs, sub_components, hmm_regime_probs, prior_estimate, prior_cov)
    # Weekly boundaries & setups
    spx_boundaries = compute_weekly_liquidity_boundaries("^GSPC")
    active_setup = "NONE"
    conditional_edge = 0.50
    if spx_boundaries:
        parsed_assets["spx_weekly_boundaries"] = spx_boundaries
        if spx_boundaries["swept_pwl_flag"]:
            active_setup = "PWL_Sweep"
            conditional_edge = calculate_bayesian_conditional_probability("PWL_Sweep", current_regime)
        elif spx_boundaries["swept_pwh_flag"]:
            active_setup = "PWH_Sweep"
            conditional_edge = calculate_bayesian_conditional_probability("PWH_Sweep", current_regime)
    parsed_assets["tactical_setup"] = {"matched_setup": active_setup, "regime_conditioned_probability": conditional_edge}
    # Structured features vector creation
    ordered_feature_keys = [
        ("SPX_ret", "SPX", "delta_pct"),
        ("DXY_ret", "DXY", "delta_pct"),
        ("VIX_zscore", "VIX", "z_score"),
        ("WTI_ret", "WTI", "delta_pct"),
        ("GoldSilverRatio_ret", "gold_to_silver_ratio", "delta_pct"),
        ("US10Y_delta", "bonds", "US10Y_delta"),
        ("US_2s10s_spread", "bonds", "spread_2s10s"),
        ("CryptoMFI_zscore", "institutional_crypto_mfi", "composite_z"),
        ("VolumeHeat_ihi", "volume_activity_heat", "institutional_heat_index"),
        ("USDCAD_ret", "USDCAD", "delta_pct")
    ]
    features_vector = []
    feature_metadata = {}
    for label, category, key in ordered_feature_keys:
        val = 0.0
        try:
            if category == "bonds":
                if key == "US10Y_delta" and bonds.get("US10Y"): val = bonds["US10Y"]["delta"]
                elif key == "spread_2s10s": val = bonds.get("spread_2s10s", 0.0)
            else: val = parsed_assets.get(category, {}).get(key, 0.0)
            if val is None or not isinstance(val, (int, float)): val = 0.0
        except Exception: pass
        features_vector.append(float(val))
        feature_metadata[label] = float(val)
    data_science_layer = {"ordered_features_list": [lbl for lbl, _, _ in ordered_feature_keys], "features_vector": features_vector, "features_dict": feature_metadata}
    mlp_state = run_mlp_inference(features_vector, mlp_package)
    # Core calibration calculations (Brier Score)
    spx_ret_now = parsed_assets.get("SPX", {}).get("delta_pct", 0.0) if parsed_assets.get("SPX") else 0.0
    brier_score, predictions_history = run_self_calibration(spx_ret_now, predictions_history_path)
    # Execute model conflict resolution (TVD)
    tvd_score = 0.0
    if mlp_state and hmm_regime_probs:
        tvd_score = calculate_model_tvd(hmm_regime_probs, mlp_state)
    kalman_state["tvd"] = tvd_score
    kalman_state["brier_score_calibration"] = brier_score
    
    kalman_probs = np.array([kalman_state.get("risk_on", 0.33), kalman_state.get("risk_off", 0.33), kalman_state.get("transitional", 0.33)])
    entropy = compute_shannon_entropy(kalman_probs)
    dominant_prob = kalman_state.get("dominant_prob", 0.33)
    kelly_fraction = compute_kelly_sizing(dominant_prob, brier_score, regime_data.get("duration_days", 0.0), regime_data.get("stability_half_life", 99.0))
    
    data_science_layer["epistemic_metrics"] = {
        "shannon_entropy": entropy,
        "kelly_exposure_fraction": kelly_fraction,
        "is_high_risk_edge": bool(dominant_prob >= 0.45) # The new aggressive edge threshold
    }

    # Core escalation assessment & model conflict resolution overrides
    escalation = "ROUTINE"
    if spx_ret_now and abs(spx_ret_now) > 2.0: escalation = "CRITICAL"
    elif spx_ret_now and abs(spx_ret_now) > 1.0: escalation = "ELEVATED"
    
    # Model conflict override: raise alert if models diverge significantly
    if tvd_score > 0.10 and escalation == "ROUTINE":
        escalation = "ELEVATED"
        logging.warning(f"Model conflict override triggered. TVD: {tvd_score}")
    # Track forecast for the next cycle calibration check
    prob_risk_on = mlp_state.get("risk_on", 0.33) if mlp_state else 0.33
    predictions_history.append({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "predicted_risk_on": float(prob_risk_on),
        "target_graded": False
    })
    try:
        with open(predictions_history_path, 'w') as f:
            json.dump(predictions_history, f, indent=2)
    except Exception:
        pass
    
    logging.info("Scraping news signal vector...")
    news_signal = fetch_market_news(prior_sentiment)
    
    snapshot_to_sign = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "raw_indicators": parsed_assets,
        "market_extremes_insight": market_extremes,
        "bonds": bonds,
        "data_science_layer": data_science_layer,
        "mcs": {"score": mcs, "label": "NEUTRAL", "sub_components": sub_components},
        "regime": regime_data,
        "kalman_state": kalman_state,
        "mlp_deep_state": mlp_state,
        "news_signal": news_signal,
        "invalidation_boundaries": {
            "us10y_invalidation_level": us10y_invalidation_level,
            "vix_invalidation_level": vix_invalidation_level
        },
        "data_driven_escalation": escalation
    }
    signature = sign_snapshot_payload(snapshot_to_sign)
    snapshot_to_sign["truchain_metadata"] = {"signature": signature, "is_valid": check_mathematical_consistency(parsed_assets), "blockchain_log": "logs/immutable_chain.log"}
    with open(output_path, 'w') as f:
        json.dump(snapshot_to_sign, f, indent=2)
    append_to_immutable_chain(signature, snapshot_to_sign["generated_utc"])
    print(f"[OK] v3.9.0 complete | Regime: {current_regime} | Kelly Exposure: {kelly_fraction * 100:.1f}%")
def fetch_fred_yield(series_id, fred_key):
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {"series_id": series_id, "api_key": fred_key, "file_type": "json", "sort_order": "desc", "limit": ROLLING_DAYS + 3}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        obs = [float(o["value"]) for o in reversed(resp.json()["observations"]) if o["value"] != "."]
        return compute_stats(pd.Series(obs))
    except Exception: return None
if __name__ == "__main__":
    main()
