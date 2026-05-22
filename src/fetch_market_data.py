#!/usr/bin/env python3
"""
fetch_market_data.py
Pulls structured market data from yfinance, FRED, and ECB Data Portal.
Writes market_snapshot.json for the macro briefing agent to consume.
Run before each 4-hour briefing cycle.
"""

import os
import json
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
    "SPX":   "^GSPC",
    "NDX":   "^NDX",
    "DAX":   "^GDAXI",
    "FTSE":  "^FTSE",
    "N225":  "^N225",
    "HSI":   "^HSI",
}

ENERGY_TICKERS = {
    "WTI":   "CL=F",
    "Brent": "BZ=F",
    "TTF":   "TTF=F",
}

FX_TICKERS = {
    "DXY":    "DX=F",
    "EURUSD": "EURUSD=X",
}

def compute_stats(series):
    if series is None or len(series) < 2:
        return None
    current  = float(series.iloc[-1])
    prev     = float(series.iloc[-2])
    delta    = current - prev
    delta_pct = (delta / prev * 100) if prev != 0 else 0
    rolling  = series.tail(ROLLING_DAYS)
    mean     = float(rolling.mean())
    std      = float(rolling.std()) if len(rolling) > 1 else 0
    z_score  = ((current - mean) / std) if std != 0 else 0
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
    logging.info("=== fetch_market_data.py starting ===")
    fred_key = get_fred_key()

    output_path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'market_snapshot.json'
    )

    # Load prior cycle state for Bayesian update and regime persistence
    prior_distribution, prior_regime = load_prior_state(output_path)

    # Fetch all market data
    equities = fetch_yfinance(EQUITY_TICKERS, "equities")
    energy   = fetch_yfinance(ENERGY_TICKERS, "energy")
    fx       = fetch_yfinance(FX_TICKERS, "fx")
    bonds    = {
        "US2Y":    fetch_fred_yield("DGS2", fred_key),
        "US10Y":   fetch_fred_yield("DGS10", fred_key),
        "Bund10Y": fetch_ecb_bund_10y(),
    }

    # Compute 2s10s spread
    us2y  = bonds.get("US2Y")
    us10y = bonds.get("US10Y")
    if us2y and us10y:
        bonds["spread_2s10s"] = round(us10y["current"] - us2y["current"], 4)
        logging.info(f"2s10s spread: {bonds['spread_2s10s']}")

    # Compute cross-asset flags
    snapshot_temp = {"equities": equities, "bonds": bonds, "energy": energy, "fx": fx}
    flags = compute_cross_asset_flags(snapshot_temp)

    # Compute MCS and sub-components
    mcs, sub_components = compute_mcs(equities, bonds, energy)
    logging.info(f"MCS: {mcs} | Sub-components: {sub_components}")

    # Classify regime with persistence filter
    current_regime = classify_regime(mcs, equities, bonds, energy)
    regime_changed = current_regime != prior_regime
    # Persistence: only confirm regime change if different from prior
    # (single-cycle change is flagged but not confirmed until next cycle)
    regime_data = {
        "current":        current_regime,
        "prior":          prior_regime,
        "changed_this_cycle": regime_changed,
        "confirmed_change":   regime_changed and prior_regime is not None,
    }
    logging.info(f"Regime: {current_regime} (prior: {prior_regime}, changed: {regime_changed})")

    # MCS label band
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

    # Compute Bayesian state distribution
    bayesian_state = compute_bayesian_state(
        mcs, sub_components, flags, prior_distribution
    )
    logging.info(
        f"Bayesian: dominant={bayesian_state['dominant_state']} "
        f"({bayesian_state['dominant_prob']:.2f}), "
        f"ambiguous={bayesian_state['ambiguous']}"
    )

    # Data-driven escalation (existing logic preserved)
    escalation = compute_data_driven_escalation(snapshot_temp, flags)

    # Escalation upgrade from MCS
    if mcs <= -60 and escalation != "CRITICAL":
        escalation = "CRITICAL"
        logging.info("Escalation upgraded to CRITICAL by MCS score.")
    elif mcs <= -20 and escalation == "ROUTINE":
        escalation = "ELEVATED"
        logging.info("Escalation upgraded to ELEVATED by MCS score.")

    # Assemble final snapshot
    snapshot = {
        "generated_utc":          datetime.now(timezone.utc).isoformat(),
        "equities":               equities,
        "energy":                 energy,
        "fx":                     fx,
        "bonds":                  bonds,
        "cross_asset_flags":      flags,
        "mcs": {
            "score":              mcs,
            "label":              mcs_label,
            "sub_components":     sub_components,
        },
        "regime":                 regime_data,
        "bayesian_state":         bayesian_state,
        "data_driven_escalation": escalation,
    }

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    logging.info(f"Snapshot written: {output_path}")
    logging.info(f"Escalation tier: {escalation}")
    print(
        f"[OK] market_snapshot.json written | "
        f"MCS: {mcs} ({mcs_label}) | "
        f"Regime: {current_regime} | "
        f"Dominant: {bayesian_state['dominant_state']} "
        f"({bayesian_state['dominant_prob']:.0%}) | "
        f"Escalation: {escalation}"
    )

if __name__ == "__main__":
    main()
