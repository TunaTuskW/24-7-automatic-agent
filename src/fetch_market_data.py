#!/usr/bin/env python3
"""
fetch_market_data.py
Pulls structured market data from yfinance, FRED, and ECB Data Portal.
Writes market_snapshot.json for the macro briefing agent to consume.
Run before each 4-hour briefing cycle.
"""

import os
import json
import joblib
import logging
import requests
import numpy as np
import pandas as pd
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
    "SPX":      "^GSPC",
    "NDX":      "^NDX",
    "DAX":      "^GDAXI",
    "FTSE":     "^FTSE",
    "N225":     "^N225",
    "HSI":      "^HSI",
    "SHANGHAI": "000001.SS",
    "SHENZHEN": "399001.SZ",
    "KOSPI":    "^KS11",
    "TASI":     "^TASI.SR",
    "DFM":      "DFMGI.AE",
}

ENERGY_TICKERS = {
    "WTI":   "CL=F",
    "Brent": "BZ=F",
    "TTF":   "TTF=F",
}

FX_TICKERS = {
    "DXY":    "DX=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "CNYUSD": "CNYUSD=X",
    "KRWUSD": "KRWUSD=X",
    "JPYUSD": "JPYUSD=X",
    "AEDUSD": "AED=X",
    "SARUSD": "SAR=X",
}

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
    # Use GARCH conditional volatility if available, else fall back to rolling std
    if garch_conditional_vol is not None and garch_conditional_vol > 0:
        delta_pct_val = delta_pct  # already computed above
        z_score = compute_garch_zscore(delta_pct_val, garch_conditional_vol)
        if z_score is None:
            z_score = ((current - mean) / std) if std != 0 else 0
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

def compute_garch_volatility(ticker_symbol, lookback_days=60):
    """
    Fit a GARCH(1,1) model on recent daily returns for a given ticker.
    Returns:
        conditional_vol: latest conditional volatility estimate (annualized %)
        vol_regime: 'LOW' / 'NORMAL' / 'ELEVATED' based on percentile vs history
        forecast_vol: one-step-ahead volatility forecast
    On failure returns None for all three — caller must handle gracefully.
    """
    try:
        from arch import arch_model
        data = yf.Ticker(ticker_symbol)
        hist = data.history(period=f"{lookback_days}d", interval="1d")
        if hist.empty or len(hist) < 20:
            logging.warning(f"GARCH: insufficient data for {ticker_symbol}")
            return None, None, None

        returns = hist["Close"].pct_change().dropna() * 100  # percent returns

        model = arch_model(
            returns,
            vol="Garch",
            p=1,
            q=1,
            mean="Zero",
            rescale=False
        )
        result = model.fit(disp="off", show_warning=False)

        # Conditional volatility — last observation
        cond_vol = float(result.conditional_volatility.iloc[-1])

        # One-step-ahead forecast
        forecast = result.forecast(horizon=1, reindex=False)
        forecast_vol = float(forecast.variance.iloc[-1, 0] ** 0.5)

        # Volatility regime — percentile of current vol vs full history
        vol_history = result.conditional_volatility.dropna()
        percentile = float((vol_history < cond_vol).mean() * 100)

        if percentile < 33:
            vol_regime = "LOW"
        elif percentile < 67:
            vol_regime = "NORMAL"
        else:
            vol_regime = "ELEVATED"

        logging.info(
            f"GARCH {ticker_symbol}: cond_vol={cond_vol:.4f}, "
            f"forecast={forecast_vol:.4f}, regime={vol_regime}"
        )
        return round(cond_vol, 4), vol_regime, round(forecast_vol, 4)

    except Exception as e:
        logging.error(f"GARCH error for {ticker_symbol}: {e}")
        return None, None, None


def compute_garch_zscore(current_return, conditional_vol):
    """
    Compute a GARCH-adjusted z-score.
    current_return: percentage return (e.g. 1.2 for +1.2%)
    conditional_vol: GARCH conditional volatility in same units
    Returns z-score or None if conditional_vol is zero or unavailable.
    """
    if conditional_vol is None or conditional_vol == 0:
        return None
    return round(current_return / conditional_vol, 3)


def fetch_garch_layer(tickers_dict):
    """
    Run GARCH for a subset of key tickers.
    Returns dict of {name: {conditional_vol, vol_regime, forecast_vol, garch_zscore}}
    Only run on tickers where GARCH is analytically meaningful.
    """
    # Only run GARCH on the most market-sensitive instruments
    garch_targets = {
        "SPX":   "^GSPC",
        "US10Y": None,      # handled via FRED — skip yfinance GARCH
        "WTI":   "CL=F",
        "DXY":   "DX=F",
    }

    results = {}
    for name, ticker in garch_targets.items():
        if ticker is None:
            continue
        cond_vol, vol_regime, forecast_vol = compute_garch_volatility(ticker)
        results[name] = {
            "conditional_vol": cond_vol,
            "vol_regime":      vol_regime,
            "forecast_vol":    forecast_vol,
        }

    return results

def normalize_to_range(value, input_min, input_max, output_min, output_max):
    """Normalize a value from input range to output range. Clamps to output bounds."""
    if input_max == input_min:
        return 0.0
    normalized = (value - input_min) / (input_max - input_min)
    result = output_min + normalized * (output_max - output_min)
    return round(max(output_min, min(output_max, result)), 3)


def compute_equity_momentum_score(equities):
    """
    Equity momentum sub-component. Range: -25 to +25.
    Weighted average z-score across SPX (40%), NDX (20%), DAX (20%), N225 (20%).
    Breadth matters — all four must agree for a strong signal.
    """
    weights = {"SPX": 0.40, "NDX": 0.20, "DAX": 0.20, "N225": 0.20}
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
    # z-score range -3 to +3 maps to -25 to +25
    return normalize_to_range(avg_z, -3.0, 3.0, -25.0, 25.0)


def compute_rate_pressure_score(bonds):
    """
    Rate pressure sub-component. Range: -25 to +25.
    Rising yields and flattening/inverted curve suppress score.
    Falling yields and steepening curve support score.
    """
    score = 0.0
    us10y = bonds.get("US10Y")
    spread = bonds.get("spread_2s10s")

    if us10y and us10y.get("delta") is not None:
        # Yield rising = negative pressure. delta in percentage points.
        # Range: -0.30 to +0.30 maps to -12.5 to +12.5
        yield_contribution = normalize_to_range(
            -us10y["delta"], -0.30, 0.30, -12.5, 12.5
        )
        score += yield_contribution

    if spread is not None:
        # Spread: deeply inverted (<-0.5) = max negative, steep (>1.5) = max positive
        # Range: -0.5 to +1.5 maps to -12.5 to +12.5
        spread_contribution = normalize_to_range(
            spread, -0.5, 1.5, -12.5, 12.5
        )
        score += spread_contribution

    return round(max(-25.0, min(25.0, score)), 3)


def compute_energy_stress_score(energy):
    """
    Energy stress sub-component. Range: -25 to +25.
    Energy price spike = negative (cost-push inflation signal).
    Energy decline = positive (demand-side relief).
    Average of WTI and Brent z-scores, inverted.
    """
    z_scores = []
    for name in ["WTI", "Brent"]:
        asset = energy.get(name)
        if asset and asset.get("z_score") is not None:
            z_scores.append(asset["z_score"])
    if not z_scores:
        return 0.0
    avg_z = sum(z_scores) / len(z_scores)
    # Invert: energy spike (positive z) = negative score
    # z range -3 to +3 maps to +25 to -25
    return normalize_to_range(-avg_z, -3.0, 3.0, -25.0, 25.0)


def compute_cross_asset_coherence_score(equities, bonds, energy):
    """
    Cross-asset coherence sub-component. Range: -25 to +25.
    Measures whether asset classes are moving in expected relationships.
    Penalizes hard when equities and bonds sell simultaneously.
    Penalizes when energy spikes alongside equity selloff.
    Rewards when relationships are internally consistent.
    """
    score = 25.0  # Start at max, penalize down
    spx = equities.get("SPX")
    us10y = bonds.get("US10Y")
    wti = energy.get("WTI")

    if not spx or not us10y:
        return 0.0

    spx_move = spx.get("delta_pct", 0)
    yield_move = us10y.get("delta", 0)

    # Equities and bonds selling simultaneously — severe penalty
    if spx_move < -1.0 and yield_move > 0.08:
        score -= 20.0

    # Equities up but yields spiking hard — tension signal
    if spx_move > 0.5 and yield_move > 0.15:
        score -= 10.0

    # Energy spiking alongside equity selloff — stagflation penalty
    if wti and wti.get("delta_pct", 0) > 2.0 and spx_move < -0.5:
        score -= 15.0

    # Reward normal risk-on coherence: equities up, yields stable/down, energy flat
    if spx_move > 0.5 and yield_move < 0.05 and (not wti or abs(wti.get("delta_pct", 0)) < 1.0):
        score = min(25.0, score + 5.0)

    return round(max(-25.0, min(25.0, score)), 3)


def compute_mcs(equities, bonds, energy):
    """
    Composite Market Condition Score (MCS). Range: -100 to +100.
    Sub-components:
      Equity momentum:      weight 30% → range -25 to +25 → contributes -30 to +30
      Rate pressure:        weight 25% → range -25 to +25 → contributes -25 to +25
      Energy stress:        weight 20% → range -25 to +25 → contributes -20 to +20
      Cross-asset coherence: weight 25% → range -25 to +25 → contributes -25 to +25

    Note: weights are applied by scaling each -25/+25 component.
    Equity: multiply by 1.2 (30/25), Rate: multiply by 1.0 (25/25),
    Energy: multiply by 0.8 (20/25), Coherence: multiply by 1.0 (25/25).
    """
    eq_score  = compute_equity_momentum_score(equities)
    rate_score = compute_rate_pressure_score(bonds)
    energy_score = compute_energy_stress_score(energy)
    coherence_score = compute_cross_asset_coherence_score(equities, bonds, energy)

    # Apply weights
    mcs = (
        eq_score       * 1.2 +
        rate_score     * 1.0 +
        energy_score   * 0.8 +
        coherence_score * 1.0
    )

    mcs = round(max(-100.0, min(100.0, mcs)), 2)

    sub_components = {
        "equity_momentum":      round(eq_score, 3),
        "rate_pressure":        round(rate_score, 3),
        "energy_stress":        round(energy_score, 3),
        "cross_asset_coherence": round(coherence_score, 3),
    }

    return mcs, sub_components


def classify_regime(mcs, equities, bonds, energy):
    """
    Classify current market regime based on MCS score and signal patterns.
    Returns one of six discrete regime labels.
    Persistence filter: regime change requires confirmation — handled by caller.
    """
    spx = equities.get("SPX", {}) or {}
    us10y = bonds.get("US10Y", {}) or {}
    wti = energy.get("WTI", {}) or {}
    dxy_data = {}  # placeholder if FX passed separately

    spx_move    = spx.get("delta_pct", 0)
    yield_move  = us10y.get("delta", 0)
    yield_level = us10y.get("current", 0)
    energy_move = wti.get("delta_pct", 0)
    spread      = bonds.get("spread_2s10s", 0) or 0

    # CRISIS: score below -60 OR simultaneous selloff with no safe haven
    if mcs <= -60:
        return "CRISIS_DISLOCATION"

    # RATE_SHOCK: yields spiking, equities selling, bonds and equities both down
    if yield_move > 0.12 and spx_move < -0.8 and mcs < -20:
        return "RATE_SHOCK"

    # STAGFLATION_STRESS: energy up, equities flat/down, yields elevated
    if energy_move > 1.5 and spx_move < 0.3 and yield_level > 4.0:
        return "STAGFLATION_STRESS"

    # DEFLATION_FEAR: equities down, yields falling fast, energy down
    if spx_move < -0.8 and yield_move < -0.10 and energy_move < -1.0:
        return "DEFLATION_FEAR"

    # LIQUIDITY_RALLY: equities up, yields falling, DXY weak
    if spx_move > 0.5 and yield_move < -0.05 and mcs > 20:
        return "LIQUIDITY_DRIVEN_RALLY"

    # RISK_ON_EXPANSION: equities up, yields stable, energy stable, mcs positive
    if mcs > 20 and spx_move > 0:
        return "RISK_ON_EXPANSION"

    # Default: neutral/transitional
    return "NEUTRAL_TRANSITIONAL"


def compute_bayesian_state(mcs, sub_components, flags, prior_distribution=None):
    """
    Compute Bayesian probability distribution across three macro states:
    risk_on, risk_off, transitional.

    Starts from prior distribution (last cycle) and updates based on
    weight-of-evidence from current signals.

    Returns updated distribution dict and dominant state label.
    """
    # Default prior if no previous cycle
    if prior_distribution is None:
        prior = {"risk_on": 0.33, "risk_off": 0.34, "transitional": 0.33}
    else:
        prior = prior_distribution.copy()

    # Evidence updates — additive adjustments to log-odds
    # Each signal shifts probability mass toward a state
    adjustments = {"risk_on": 0.0, "risk_off": 0.0, "transitional": 0.0}

    # MCS as primary signal
    if mcs > 40:
        adjustments["risk_on"] += 0.25
        adjustments["risk_off"] -= 0.15
    elif mcs > 15:
        adjustments["risk_on"] += 0.12
        adjustments["transitional"] += 0.05
    elif mcs < -40:
        adjustments["risk_off"] += 0.25
        adjustments["risk_on"] -= 0.15
    elif mcs < -15:
        adjustments["risk_off"] += 0.12
        adjustments["transitional"] += 0.05
    else:
        adjustments["transitional"] += 0.10

    # Sub-component signals
    eq = sub_components.get("equity_momentum", 0)
    coherence = sub_components.get("cross_asset_coherence", 0)

    if eq > 15:
        adjustments["risk_on"] += 0.08
    elif eq < -15:
        adjustments["risk_off"] += 0.08

    if coherence < -10:
        adjustments["risk_off"] += 0.10
        adjustments["transitional"] += 0.05

    # Cross-asset flags as strong evidence
    for flag in flags:
        if "simultaneously" in flag.lower():
            adjustments["risk_off"] += 0.15
        if "stagflation" in flag.lower():
            adjustments["risk_off"] += 0.10
        if "divergence" in flag.lower():
            adjustments["transitional"] += 0.08

    # Apply adjustments to prior using soft update
    # Use learning rate to prevent overcorrection in single cycle
    learning_rate = 0.4
    updated = {}
    for state in ["risk_on", "risk_off", "transitional"]:
        updated[state] = prior[state] + learning_rate * adjustments[state]
        updated[state] = max(0.05, updated[state])  # floor at 5%

    # Normalize to sum to 1.0
    total = sum(updated.values())
    for state in updated:
        updated[state] = round(updated[state] / total, 3)

    # Determine dominant state
    dominant = max(updated, key=updated.get)
    dominant_prob = updated[dominant]

    # Ambiguity flag: no state exceeds 50%
    ambiguous = dominant_prob < 0.50

    return {
        "risk_on":       updated["risk_on"],
        "risk_off":      updated["risk_off"],
        "transitional":  updated["transitional"],
        "dominant_state": dominant,
        "dominant_prob":  dominant_prob,
        "ambiguous":      ambiguous,
    }

def load_prior_state(snapshot_path):
    """
    Load Bayesian distribution and regime from previous cycle's snapshot.
    Returns (prior_distribution, prior_regime) or (None, None) if unavailable.
    """
    try:
        if os.path.exists(snapshot_path):
            with open(snapshot_path, 'r') as f:
                prior = json.load(f)
            bayes = prior.get("bayesian_state")
            regime = prior.get("regime", {}).get("current")
            if bayes:
                dist = {
                    "risk_on":      bayes.get("risk_on", 0.33),
                    "risk_off":     bayes.get("risk_off", 0.34),
                    "transitional": bayes.get("transitional", 0.33),
                }
                return dist, regime
    except Exception as e:
        logging.warning(f"Could not load prior state: {e}")
    return None, None

def load_hmm_model():
    """
    Load pre-trained HMM model package from disk.
    Returns model_package dict or None if unavailable.
    """
    model_path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'hmm_model.pkl'
    )
    try:
        if os.path.exists(model_path):
            package = joblib.load(model_path)
            logging.info(
                f"HMM loaded — trained at {package.get('trained_at', 'unknown')}"
            )
            return package
    except Exception as e:
        logging.error(f"HMM load failed: {e}")
    return None


def run_hmm_inference(equities, bonds, energy, fx, garch_layer, hmm_package):
    """
    Run HMM inference on current market snapshot.
    Returns:
        regime_probs:     dict of {regime_label: probability}
        dominant_regime:  string label
        transition_risk:  probability of regime change next cycle
        state_sequence:   most likely current hidden state id
    Falls back to rule-based classifier if HMM unavailable.
    """
    if hmm_package is None:
        logging.warning("HMM unavailable — falling back to rule-based classifier")
        return None, None, None, None

    try:
        hmm          = hmm_package["hmm"]
        scaler       = hmm_package["scaler"]
        state_labels = hmm_package["state_labels"]
        feature_names = hmm_package["feature_names"]

        # Build observation vector matching training features
        spx   = equities.get("SPX") or {}
        wti   = energy.get("WTI") or {}
        dxy   = fx.get("DXY") or {}
        us10y = bonds.get("US10Y") or {}
        spread = bonds.get("spread_2s10s") or 0.0

        spx_ret      = spx.get("delta_pct", 0.0)
        wti_ret      = wti.get("delta_pct", 0.0)
        dxy_ret      = dxy.get("delta_pct", 0.0)
        us10y_delta  = us10y.get("delta", 0.0)

        # GARCH vol for SPX
        spx_garch_vol = 0.0
        if garch_layer and "SPX" in garch_layer:
            spx_garch_vol = garch_layer["SPX"].get("conditional_vol") or 0.0

        # Spread delta — approximate from current snapshot
        spread_delta = 0.0  # single-observation inference; use 0 as neutral

        obs = np.array([[
            spx_ret,
            wti_ret,
            dxy_ret,
            spx_garch_vol,
            us10y_delta,
            spread_delta,
        ]])

        obs_scaled = scaler.transform(obs)

        # Posterior state probabilities for current observation
        # Use score_samples to get log-likelihood, then compute posteriors
        _, posteriors = hmm.score_samples(obs_scaled)
        state_probs = posteriors[0]  # shape: (n_states,)

        # Map state indices to regime labels
        regime_probs = {}
        for state_id, prob in enumerate(state_probs):
            label = state_labels.get(state_id, f"STATE_{state_id}")
            regime_probs[label] = round(float(prob), 4)

        # Dominant regime
        dominant_state_id = int(np.argmax(state_probs))
        dominant_regime = state_labels.get(dominant_state_id, "NEUTRAL_TRANSITIONAL")

        # Transition risk — probability of NOT staying in dominant state next cycle
        stay_prob = float(hmm.transmat_[dominant_state_id, dominant_state_id])
        transition_risk = round(1.0 - stay_prob, 4)

        logging.info(
            f"HMM inference: dominant={dominant_regime} "
            f"({state_probs[dominant_state_id]:.3f}), "
            f"transition_risk={transition_risk:.3f}"
        )

        return regime_probs, dominant_regime, transition_risk, dominant_state_id

    except Exception as e:
        logging.error(f"HMM inference failed: {e}")
        return None, None, None, None

def run_kalman_filter(mcs, sub_components, hmm_regime_probs,
                      prior_state_estimate=None, prior_covariance=None):
    """
    Kalman filter for macro state tracking.
    
    State vector: [risk_on, risk_off, transitional] probabilities
    Observation: derived from MCS sub-components and HMM regime probabilities
    
    Returns:
        state_estimate:  dict with risk_on, risk_off, transitional probabilities
        covariance:      scalar uncertainty measure (trace of covariance matrix)
        ambiguous:       bool — True when covariance exceeds threshold
        dominant_state:  string label
        dominant_prob:   float
    """
    # State dimension
    n = 3  # risk_on, risk_off, transitional

    # Initialize prior
    if prior_state_estimate is None:
        x = np.array([1/3, 1/3, 1/3])
    else:
        x = np.array([
            prior_state_estimate.get("risk_on", 1/3),
            prior_state_estimate.get("risk_off", 1/3),
            prior_state_estimate.get("transitional", 1/3),
        ])

    if prior_covariance is None:
        P = np.eye(n) * 0.1
    else:
        P = np.array(prior_covariance).reshape(n, n)

    # Process noise — how much state can change between cycles
    # Larger = more responsive to new evidence, smaller = more stable
    Q = np.eye(n) * 0.02

    # State transition matrix — near-identity (state is persistent)
    F = np.array([
        [0.92, 0.04, 0.04],
        [0.04, 0.92, 0.04],
        [0.04, 0.04, 0.92],
    ])

    # Observation matrix — maps state to observation space
    H = np.eye(n)

    # Measurement noise — reflects uncertainty in our observation derivation
    R = np.eye(n) * 0.05

    # ── PREDICT ───────────────────────────────────────────────────────────────
    x_pred = F @ x
    P_pred = F @ P @ F.T + Q

    # ── BUILD OBSERVATION VECTOR ───────────────────────────────────────────────
    # Derive observation from MCS and HMM outputs

    # MCS contribution
    if mcs > 30:
        mcs_obs = np.array([0.65, 0.15, 0.20])
    elif mcs > 10:
        mcs_obs = np.array([0.45, 0.25, 0.30])
    elif mcs > -10:
        mcs_obs = np.array([0.25, 0.35, 0.40])
    elif mcs > -30:
        mcs_obs = np.array([0.15, 0.55, 0.30])
    else:
        mcs_obs = np.array([0.10, 0.75, 0.15])

    # HMM contribution — if available, weight it heavily
    if hmm_regime_probs is not None:
        risk_on_labels = {"RISK_ON_EXPANSION", "LIQUIDITY_DRIVEN_RALLY"}
        risk_off_labels = {
            "STAGFLATION_STRESS", "RATE_SHOCK",
            "DEFLATION_FEAR", "CRISIS_DISLOCATION"
        }
        hmm_risk_on  = sum(
            v for k, v in hmm_regime_probs.items()
            if any(lab in k for lab in risk_on_labels)
        )
        hmm_risk_off = sum(
            v for k, v in hmm_regime_probs.items()
            if any(lab in k for lab in risk_off_labels)
        )
        hmm_trans = max(0.0, 1.0 - hmm_risk_on - hmm_risk_off)
        hmm_obs = np.array([hmm_risk_on, hmm_risk_off, hmm_trans])

        # Blend MCS and HMM observations — HMM gets 60% weight
        z = 0.4 * mcs_obs + 0.6 * hmm_obs
    else:
        z = mcs_obs

    # Normalize observation to sum to 1
    z = np.clip(z, 0.01, 0.99)
    z = z / z.sum()

    # ── UPDATE ────────────────────────────────────────────────────────────────
    innovation = z - H @ x_pred
    S = H @ P_pred @ H.T + R
    K = P_pred @ H.T @ np.linalg.inv(S)

    x_updated = x_pred + K @ innovation
    P_updated = (np.eye(n) - K @ H) @ P_pred

    # Clip and renormalize
    x_updated = np.clip(x_updated, 0.01, 0.99)
    x_updated = x_updated / x_updated.sum()

    # Uncertainty measure — trace of covariance matrix
    uncertainty = float(np.trace(P_updated))

    # Ambiguity threshold — tuned to flag genuine uncertainty
    ambiguous = uncertainty > 0.15 or float(np.max(x_updated)) < 0.50

    states = ["risk_on", "risk_off", "transitional"]
    dominant_idx = int(np.argmax(x_updated))
    dominant_state = states[dominant_idx]
    dominant_prob = float(x_updated[dominant_idx])

    logging.info(
        f"Kalman: risk_on={x_updated[0]:.3f}, risk_off={x_updated[1]:.3f}, "
        f"transitional={x_updated[2]:.3f}, uncertainty={uncertainty:.4f}, "
        f"ambiguous={ambiguous}"
    )

    return {
        "risk_on":          round(float(x_updated[0]), 3),
        "risk_off":         round(float(x_updated[1]), 3),
        "transitional":     round(float(x_updated[2]), 3),
        "dominant_state":   dominant_state,
        "dominant_prob":    round(dominant_prob, 3),
        "uncertainty":      round(uncertainty, 4),
        "ambiguous":        ambiguous,
        "covariance_matrix": P_updated.tolist(),
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
    logging.info("=== fetch_market_data.py v2.0.0 starting ===")
    fred_key = get_fred_key()

    output_path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'market_snapshot.json'
    )

    # Load prior cycle state
    prior_distribution, prior_regime = load_prior_state(output_path)

    # Load prior Kalman state if available
    prior_kalman_estimate = None
    prior_kalman_covariance = None
    try:
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                prior_snap = json.load(f)
            ks = prior_snap.get("kalman_state", {})
            if ks:
                prior_kalman_estimate = {
                    k: ks[k] for k in ["risk_on", "risk_off", "transitional"]
                    if k in ks
                }
                prior_kalman_covariance = ks.get("covariance_matrix")
    except Exception as e:
        logging.warning(f"Could not load prior Kalman state: {e}")

    # Load HMM model
    hmm_package = load_hmm_model()

    # Fetch GARCH layer first — needed for enhanced z-scores
    logging.info("Running GARCH layer...")
    garch_layer = fetch_garch_layer({})

    # Fetch market data — pass GARCH vol to compute_stats where available
    logging.info("Fetching equity data...")
    equities_raw = {}
    for name, ticker in EQUITY_TICKERS.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="10d", interval="1d")
            if hist.empty:
                logging.warning(f"yfinance: no data for {name} ({ticker})")
                equities_raw[name] = None
                continue
            # Pass GARCH vol for GARCH-adjusted z-score on key indices
            garch_vol = None
            if name in garch_layer and garch_layer[name]["conditional_vol"]:
                garch_vol = garch_layer[name]["conditional_vol"]
            stats = compute_stats(hist["Close"], garch_conditional_vol=garch_vol)
            # Attach GARCH metadata
            if stats and name in garch_layer:
                stats["vol_regime"]   = garch_layer[name].get("vol_regime")
                stats["forecast_vol"] = garch_layer[name].get("forecast_vol")
            equities_raw[name] = stats
            logging.info(f"yfinance: {name} = {stats['current'] if stats else 'None'}")
        except Exception as e:
            logging.error(f"yfinance error for {name}: {e}")
            equities_raw[name] = None

    equities = equities_raw

    logging.info("Fetching energy data...")
    energy = {}
    for name, ticker in ENERGY_TICKERS.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="10d", interval="1d")
            if hist.empty:
                energy[name] = None
                continue
            garch_vol = None
            if name in garch_layer and garch_layer[name]["conditional_vol"]:
                garch_vol = garch_layer[name]["conditional_vol"]
            stats = compute_stats(hist["Close"], garch_conditional_vol=garch_vol)
            if stats and name in garch_layer:
                stats["vol_regime"]   = garch_layer[name].get("vol_regime")
                stats["forecast_vol"] = garch_layer[name].get("forecast_vol")
            energy[name] = stats
        except Exception as e:
            logging.error(f"Energy error {name}: {e}")
            energy[name] = None

    logging.info("Fetching FX data...")
    fx = {}
    for name, ticker in FX_TICKERS.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="10d", interval="1d")
            if hist.empty:
                fx[name] = None
                continue
            garch_vol = None
            if name in garch_layer and garch_layer[name]["conditional_vol"]:
                garch_vol = garch_layer[name]["conditional_vol"]
            fx[name] = compute_stats(hist["Close"], garch_conditional_vol=garch_vol)
        except Exception as e:
            logging.error(f"FX error {name}: {e}")
            fx[name] = None

    logging.info("Fetching bond yields...")
    bonds = {
        "US2Y":    fetch_fred_yield("DGS2", fred_key),
        "US10Y":   fetch_fred_yield("DGS10", fred_key),
        "Bund10Y": fetch_ecb_bund_10y(),
    }

    # 2s10s spread
    us2y  = bonds.get("US2Y")
    us10y = bonds.get("US10Y")
    if us2y and us10y:
        bonds["spread_2s10s"] = round(us10y["current"] - us2y["current"], 4)
        logging.info(f"2s10s spread: {bonds['spread_2s10s']}")

    # Cross-asset flags
    snapshot_temp = {"equities": equities, "bonds": bonds, "energy": energy, "fx": fx}
    flags = compute_cross_asset_flags(snapshot_temp)

    # MCS
    mcs, sub_components = compute_mcs(equities, bonds, energy)
    logging.info(f"MCS: {mcs} | Sub-components: {sub_components}")

    # MCS label
    if mcs >= 60:
        mcs_label = "EXPANSION"
    elif mcs >= 20:
        mcs_label = "NEUTRAL_POSITIVE"
    elif mcs >= -19:
        mcs_label = "NEUTRAL"
    elif mcs >= -60:
        mcs_label = "STRESS"
    else:
        mcs_label = "CRISIS"

    # HMM regime inference
    hmm_regime_probs, hmm_dominant_regime, transition_risk, hmm_state_id =         run_hmm_inference(equities, bonds, energy, fx, garch_layer, hmm_package)

    # Regime data — use HMM if available, else rule-based fallback
    if hmm_dominant_regime is not None:
        current_regime = hmm_dominant_regime
        regime_source  = "HMM"
    else:
        current_regime = classify_regime(mcs, equities, bonds, energy)
        regime_source  = "RULE_BASED"

    regime_changed = current_regime != prior_regime
    regime_data = {
        "current":            current_regime,
        "prior":              prior_regime,
        "source":             regime_source,
        "changed_this_cycle": regime_changed,
        "confirmed_change":   regime_changed and prior_regime is not None,
        "probabilities":      hmm_regime_probs,
        "transition_risk":    transition_risk,
    }
    logging.info(
        f"Regime: {current_regime} [{regime_source}] "
        f"(prior: {prior_regime}, changed: {regime_changed}, "
        f"transition_risk: {transition_risk})"
    )

    # Kalman filter state tracking
    kalman_state = run_kalman_filter(
        mcs, sub_components, hmm_regime_probs,
        prior_kalman_estimate, prior_kalman_covariance
    )

    # Escalation
    escalation = compute_data_driven_escalation(snapshot_temp, flags)

    # MCS escalation overrides
    if mcs <= -60 and escalation != "CRITICAL":
        escalation = "CRITICAL"
        logging.info("Escalation upgraded to CRITICAL by MCS score.")
    elif mcs <= -20 and escalation == "ROUTINE":
        escalation = "ELEVATED"
        logging.info("Escalation upgraded to ELEVATED by MCS score.")

    # Transition risk escalation override
    if transition_risk is not None and transition_risk > 0.35 and escalation == "ROUTINE":
        escalation = "ELEVATED"
        logging.info(
            f"Escalation upgraded to ELEVATED by HMM transition risk "
            f"({transition_risk:.2f} > 0.35)."
        )

    # GARCH forward volatility summary for output
    garch_summary = {}
    for name, data in garch_layer.items():
        if data:
            garch_summary[name] = {
                "conditional_vol": data.get("conditional_vol"),
                "vol_regime":      data.get("vol_regime"),
                "forecast_vol":    data.get("forecast_vol"),
            }

    # Assemble snapshot
    snapshot = {
        "generated_utc":          datetime.now(timezone.utc).isoformat(),
        "equities":               equities,
        "energy":                 energy,
        "fx":                     fx,
        "bonds":                  bonds,
        "cross_asset_flags":      flags,
        "mcs": {
            "score":          mcs,
            "label":          mcs_label,
            "sub_components": sub_components,
        },
        "regime":         regime_data,
        "kalman_state":   kalman_state,
        "garch_layer":    garch_summary,
        "data_driven_escalation": escalation,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    logging.info(f"Snapshot written: {output_path}")
    print(
        f"[OK] market_snapshot.json written | "
        f"MCS: {mcs} ({mcs_label}) | "
        f"Regime: {current_regime} [{regime_source}] | "
        f"Kalman: {kalman_state['dominant_state']} "
        f"({kalman_state['dominant_prob']:.0%}) | "
        f"Transition risk: {transition_risk:.0%} | "
        f"Escalation: {escalation}"
        if transition_risk is not None else
        f"[OK] market_snapshot.json written | "
        f"MCS: {mcs} ({mcs_label}) | "
        f"Regime: {current_regime} [{regime_source}] | "
        f"Kalman: {kalman_state['dominant_state']} "
        f"({kalman_state['dominant_prob']:.0%}) | "
        f"Escalation: {escalation}"
    )

if __name__ == "__main__":
    main()
