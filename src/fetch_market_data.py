#!/usr/bin/env python3
"""
fetch_market_data.py - v2.7.0
Pulls multi-source parallel data from yfinance, FRED, and ECB.
Performs TruChain verification, executes deep MLP and HMM inferences, 
and outputs data-science-ready outputs.
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
from datetime import datetime, timezone, timedelta
try:
    import yfinance as yf
except ImportError:
    raise ImportError("Install yfinance: pip install yfinance")
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), '..', 'logs', 'fetch_market_data.log'),
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
# Consolidated Multi-Source Ticker Schema
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
    "VIX": "^VIX",
    # Institutional Digital Asset Flow
    "IBIT": "IBIT",      
    "ETHA": "ETHA",      
    "COIN": "COIN"       
}
garch_targets = {
    "SPX":   "^GSPC",
    "WTI":   "CL=F",
    "DXY":   "DX-Y.NYB",   
}
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
    model_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'mlp_model.pkl')
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
    # Normalizes z-score range -3 to 3 -> -25 to 25
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
        spread_delta = 0.0
        # Backtest mapped features validation
        gsr_val = 0.0
        gold = equities.get("Gold")
        silver = equities.get("Silver")
        if gold and silver and silver.get("current", 0) > 0:
            gsr_val = ((gold["current"]/silver["current"]) - (gold["prev"]/silver["prev"])) / (gold["prev"]/silver["prev"]) * 100
        obs = np.array([[spx_ret, dxy_ret, spx_garch_vol, wti_ret, gsr_val, us10y_delta, bonds.get("spread_2s10s", 0.0), 0.0, fx.get("USDCAD", {}).get("delta_pct", 0.0)]])
        obs_scaled = scaler.transform(obs)
        _, posteriors = hmm.score_samples(obs_scaled)
        state_probs = posteriors[0]
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
    
    # Obs derivation
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
    states = ["risk_on", "risk_off", "transitional"]
    dominant_idx = int(np.argmax(x_updated))
    return {
        "risk_on":          round(float(x_updated[0]), 3),
        "risk_off":         round(float(x_updated[1]), 3),
        "transitional":     round(float(x_updated[2]), 3),
        "dominant_state":   states[dominant_idx],
        "dominant_prob":    round(float(x_updated[dominant_idx]), 3),
        "uncertainty":      round(uncertainty, 4),
        "ambiguous":        uncertainty > 0.15 or float(np.max(x_updated)) < 0.50,
        "covariance_matrix": P_updated.tolist()
    }
def main():
    logging.info("=== fetch_market_data.py v2.7.0 starting ===")
    fred_key = get_fred_key()
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_snapshot.json')
    # Load prior Kalman state
    prior_estimate, prior_cov, prior_regime = None, None, None
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                prior = json.load(f)
            prior_regime = prior.get("regime", {}).get("current")
            ks = prior.get("kalman_state", {})
            if ks:
                prior_estimate = {k: ks[k] for k in ["risk_on", "risk_off", "transitional"] if k in ks}
                prior_cov = ks.get("covariance_matrix")
        except Exception:
            pass
    # Load pre-trained packages
    hmm_model_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'hmm_model.pkl')
    hmm_package = joblib.load(hmm_model_path) if os.path.exists(hmm_model_path) else None
    mlp_package = load_mlp_model()
    logging.info("Fitting live GARCH vol models...")
    garch_layer = {}
    for name, ticker in garch_targets.items():
        cond_vol, vol_regime, forecast_vol = compute_garch_volatility(ticker, lookback_days=250)
        garch_layer[name] = {"conditional_vol": cond_vol, "vol_regime": vol_regime, "forecast_vol": forecast_vol}
    logging.info("Parallel downloading complete ticker universe...")
    tickers_list = list(ALL_YF_TICKERS.values())
    raw_data = yf.download(tickers_list, period="15d", interval="1d", group_by="ticker", progress=False)
    parsed_assets = {}
    for name, symbol in ALL_YF_TICKERS.items():
        try:
            # MultiIndex safe verification check
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
    # Execute deep MLP classifier state
    mlp_state = run_mlp_inference(features_vector, mlp_package)
    # Ingest baseline MCS score & HMM inference
    mcs, sub_components = compute_mcs(parsed_assets, bonds, parsed_assets)
    hmm_regime_probs, hmm_dominant, transition_risk, _ = run_hmm_inference(parsed_assets, bonds, parsed_assets, parsed_assets, garch_layer, hmm_package)
    current_regime = hmm_dominant if hmm_dominant else "NEUTRAL_TRANSITIONAL"
    regime_changed = current_regime != prior_regime
    regime_data = {
        "current": current_regime, "prior": prior_regime, "changed_this_cycle": regime_changed,
        "confirmed_change": regime_changed and prior_regime is not None, "probabilities": hmm_regime_probs, "transition_risk": transition_risk
    }
    kalman_state = run_kalman_filter(mcs, sub_components, hmm_regime_probs, prior_estimate, prior_cov)
    # Core escalation assessment
    escalation = "ROUTINE"
    spx = parsed_assets.get("SPX")
    if spx and abs(spx["delta_pct"]) > 2.0: escalation = "CRITICAL"
    elif spx and abs(spx["delta_pct"]) > 1.0: escalation = "ELEVATED"
    # Assemble snapshot to sign
    snapshot_to_sign = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "raw_indicators": parsed_assets, "bonds": bonds,
        "data_science_layer": data_science_layer, "mcs": {"score": mcs, "label": "NEUTRAL", "sub_components": sub_components},
        "regime": regime_data, "kalman_state": kalman_state, "mlp_deep_state": mlp_state, "data_driven_escalation": escalation
    }
    signature = sign_snapshot_payload(snapshot_to_sign)
    snapshot_to_sign["truchain_metadata"] = {"signature": signature, "is_valid": check_mathematical_consistency(parsed_assets), "blockchain_log": "logs/immutable_chain.log"}
    with open(output_path, 'w') as f:
        json.dump(snapshot_to_sign, f, indent=2)
    append_to_immutable_chain(signature, snapshot_to_sign["generated_utc"])
    print(f"[OK] v2.7.0 complete | HMM Regime: {current_regime} | Deep MLP: {mlp_state.get('dominant_state') if mlp_state else 'None'}")
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
