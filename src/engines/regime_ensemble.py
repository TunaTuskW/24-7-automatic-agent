from typing import Dict, Tuple, Any, List
import numpy as np

class RegimeEnsemble:
    """
    Bayesian Fusion Layer that replaces the legacy HMM.
    Takes discrete signals from sub-engines and outputs a probabilistic regime state.
    """
    def __init__(self):
        # Weights for the Bayesian fusion
        self.weights = {
            "trend": 0.35,      # UT Bot LinReg Trend
            "smc": 0.25,        # Smart Money Concepts bias
            "session": 0.15,    # ORB / TD9 Session exhaustion
            "liquidity": 0.10,  # Magnet target
            "macro": 0.15       # Yields, VIX, etc.
        }

    def compute(self, 
                trend_state: dict, 
                smc_state: dict, 
                session_state: dict, 
                liquidity_state: dict, 
                features_dict: dict) -> Tuple[Dict[str, float], str, float, Any]:
        """
        Computes the regime probabilities.
        Returns:
            probs (Dict[str, float]): Map of regime probabilities
            dominant (str): Name of dominant regime
            transition_risk (float): Risk of regime transition
            raw: None
        """
        
        # 1. Trend Signal (-1 to 1)
        trend_val = 0.0
        if trend_state.get("trend_state") == "UPTREND":
            trend_val = trend_state.get("trend_conviction", 0.8)
        elif trend_state.get("trend_state") == "DOWNTREND":
            trend_val = -trend_state.get("trend_conviction", 0.8)
            
        # 2. SMC Signal (-1 to 1)
        smc_val = float(smc_state.get("smc_bias", 0))
        
        # 3. Session / ORB / TD9 (-1 to 1)
        session_val = 0.0
        if session_state.get("td9_exhaustion", False):
            session_val = float(session_state.get("td9_direction", 0)) * 0.8
        elif session_state.get("orb_signal", 0) != 0:
            session_val = float(session_state.get("orb_signal", 0)) * 0.5
            
        # 4. Liquidity Magnet (-1 to 1)
        liq_val = 0.0
        if liquidity_state.get("magnet_target") == "UP":
            liq_val = 0.8
        elif liquidity_state.get("magnet_target") == "DOWN":
            liq_val = -0.8
            
        # 5. Macro (VIX, Spread) (-1 to 1)
        macro_val = 0.0
        vix_z = features_dict.get("vix_zscore", 0.0)
        spread = features_dict.get("spread_level", 0.0)
        
        if vix_z > 1.5:
            macro_val -= 0.5
        elif vix_z < -1.0:
            macro_val += 0.3
            
        if spread < -0.5: # Inverted
            macro_val -= 0.3
            
        # Bayesian Fusion (Weighted Average of signals)
        total_weight = sum(self.weights.values())
        raw_score = (
            self.weights["trend"] * trend_val +
            self.weights["smc"] * smc_val +
            self.weights["session"] * session_val +
            self.weights["liquidity"] * liq_val +
            self.weights["macro"] * macro_val
        ) / total_weight
        
        # Map raw_score (-1 to 1) to probabilities
        # raw_score > 0.4 -> RISK_ON_EXPANSION
        # raw_score > 0.1 -> LIQUIDITY_DRIVEN_RALLY
        # raw_score < -0.4 -> CRISIS_DISLOCATION / VOLATILITY_EXPANSION
        # raw_score < -0.1 -> DEFENSIVE_RISK_OFF
        # else -> NEUTRAL_TRANSITIONAL
        
        probs = {
            "RISK_ON_EXPANSION": 0.0,
            "LIQUIDITY_DRIVEN_RALLY": 0.0,
            "NEUTRAL_TRANSITIONAL": 0.0,
            "DEFENSIVE_RISK_OFF": 0.0,
            "VOLATILITY_EXPANSION": 0.0
        }
        
        if raw_score >= 0.3:
            probs["RISK_ON_EXPANSION"] = 0.6
            probs["LIQUIDITY_DRIVEN_RALLY"] = 0.3
            probs["NEUTRAL_TRANSITIONAL"] = 0.1
        elif raw_score >= 0.05:
            probs["LIQUIDITY_DRIVEN_RALLY"] = 0.5
            probs["NEUTRAL_TRANSITIONAL"] = 0.4
            probs["RISK_ON_EXPANSION"] = 0.1
        elif raw_score <= -0.3:
            probs["VOLATILITY_EXPANSION"] = 0.6
            probs["DEFENSIVE_RISK_OFF"] = 0.3
            probs["NEUTRAL_TRANSITIONAL"] = 0.1
        elif raw_score <= -0.05:
            probs["DEFENSIVE_RISK_OFF"] = 0.5
            probs["NEUTRAL_TRANSITIONAL"] = 0.4
            probs["VOLATILITY_EXPANSION"] = 0.1
        else:
            probs["NEUTRAL_TRANSITIONAL"] = 0.7
            probs["LIQUIDITY_DRIVEN_RALLY"] = 0.15
            probs["DEFENSIVE_RISK_OFF"] = 0.15
            
        dominant_regime = max(probs.items(), key=lambda x: x[1])[0]
        
        # Transition risk is high if raw_score is near 0 or signals conflict heavily
        variance = np.var([trend_val, smc_val, session_val, liq_val, macro_val])
        transition_risk = min(1.0, variance * 1.5)
        
        return probs, dominant_regime, transition_risk, None
