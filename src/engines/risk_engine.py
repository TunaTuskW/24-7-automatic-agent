import numpy as np
import math
import os
from typing import Dict, Any
from src.observability.logger import get_logger
from src.schemas.models import KalmanState

logger = get_logger("risk-engine")

class RiskEngine:
    def run_kalman_filter(self, mcs: float, sub_components: Dict, hmm_regime_probs: Dict, prior_state=None, prior_cov=None) -> KalmanState:
        logger.info("Running Kalman Filter")
        try:
            n = 3
            x = np.array([1/3, 1/3, 1/3]) if prior_state is None else np.array(prior_state)
            P = np.eye(n) * 0.1 if prior_cov is None else np.array(prior_cov).reshape(n, n)
            Q = np.eye(n) * 0.02
            F = np.array([[0.92, 0.04, 0.04], [0.04, 0.92, 0.04], [0.04, 0.04, 0.92]])
            
            hmm_risk_on = hmm_regime_probs.get("RISK_ON_EXPANSION", 0.0) + hmm_regime_probs.get("LIQUIDITY_DRIVEN_RALLY", 0.0)
            
            # Map all known stress and shock states to risk_off
            risk_off_states = ["DEFENSIVE_RISK_OFF", "VOLATILITY_EXPANSION"]
            hmm_risk_off = sum(hmm_regime_probs.get(s, 0.0) for s in risk_off_states)
            
            # Add dynamic checking for indexed states like COMMODITY_SHOCK_4
            for state_name, prob in hmm_regime_probs.items():
                if any(state_name.startswith(base) for base in risk_off_states) and state_name not in risk_off_states:
                    hmm_risk_off += prob
                elif any(state_name.startswith(base) for base in ["RISK_ON", "LIQUIDITY"]) and state_name not in ["RISK_ON_EXPANSION", "LIQUIDITY_DRIVEN_RALLY"]:
                    hmm_risk_on += prob
                    
            hmm_trans = max(0.0, 1.0 - hmm_risk_on - hmm_risk_off)
            
            z = np.array([hmm_risk_on, hmm_risk_off, hmm_trans])
            if z.sum() > 0:
                z /= z.sum()
            else:
                z = np.array([1/3, 1/3, 1/3])
            
            x_pred = F @ x
            P_pred = F @ P @ F.T + Q
            
            H = np.eye(n)
            
            # Dynamic measurement noise to prevent sudden 1-bar regime jumps
            is_sudden_fear = (z[1] > 0.6) and (x[1] < 0.3)
            if is_sudden_fear:
                R = np.eye(n) * 0.25
                logger.info("Sudden fear spike detected. Inflating measurement noise to enforce multi-bar confirmation.")
            else:
                R = np.eye(n) * 0.05
            
            S = H @ P_pred @ H.T + R
            K = P_pred @ H.T @ np.linalg.inv(S)
            
            x_updated = x_pred + K @ (z - H @ x_pred)
            x_updated = np.clip(x_updated, 0.01, 0.99)
            x_updated /= x_updated.sum()
            
            P_updated = (np.eye(n) - K @ H) @ P_pred
            
            max_prob = float(np.max(x_updated))
            is_ambiguous = max_prob < 0.60
            
            states = ["risk_on", "risk_off", "transitional"]
            dominant_idx = int(np.argmax(x_updated))
            
            return KalmanState(
                risk_on=round(float(x_updated[0]), 3),
                risk_off=round(float(x_updated[1]), 3),
                transitional=round(float(x_updated[2]), 3),
                dominant_state=states[dominant_idx],
                dominant_prob=round(float(x_updated[dominant_idx]), 3),
                is_ambiguous=bool(is_ambiguous),
                covariance_matrix=P_updated.tolist(),
                probabilities=x_updated.tolist()
            )
        except Exception as e:
            logger.error(f"Kalman filter failed: {e}")
            return KalmanState()

    def compute_shannon_entropy(self, probs: np.ndarray) -> float:
        try:
            probs = np.clip(probs, 1e-9, 1.0)
            entropy = -np.sum(probs * np.log2(probs))
            return round(float(entropy), 3)
        except Exception:
            return 1.58

    def compute_kelly_sizing(self, max_prob: float, dominant_state: str, brier_score: float, duration_days: float = 0.0, half_life: float = 99.0, sentiment_multiplier: float = 1.0, is_capitulation_override: bool = False, is_momentum_override: bool = False, is_black_swan: bool = False, is_bull_trap: bool = False, hmm_regime: str = "UNKNOWN", current_ihi: float = 0.0, consensus_score: float = 0.0, conviction_threshold: float = 0.60) -> float:
        logger.info(f"Computing Kelly size (prob: {max_prob}, state: {dominant_state}, brier: {brier_score}, consensus: {consensus_score}, threshold: {conviction_threshold})")
        
        if is_bull_trap:
            logger.warning("Bull Trap Override Active: MLP Prob > 0.80 is historically inversely calibrated. Inverting to contrarian bearish.")
            max_prob = 1.0 - max_prob
            
        is_short_bet = False
        effective_prob = max_prob
        if max_prob < 0.5:
            is_short_bet = True
            effective_prob = 1.0 - max_prob
            
        # High Conviction base probability threshold (need at least threshold win rate expectation to play)
        edge = effective_prob - conviction_threshold
        if edge <= 0:
            logger.info(f"No high conviction edge (prob {effective_prob:.3f} <= {conviction_threshold}). Returning 0.0 Kelly allocation.")
            return 0.0
        
        win_rate = effective_prob
        loss_rate = 1.0 - win_rate
        base_fraction = win_rate - (loss_rate / 2.0)
        
        # Baseline Risk Tolerance: High volatility regimes mathematically generate noise.
        # We relax the Brier penalty if the model correctly identified a Risk Off regime.
        # Calibration Penalty (Brier Score scaling) - bypassed by momentum override
        if is_momentum_override:
            calibration_penalty = 1.0
        elif dominant_state == "risk_off":
            if brier_score > 0.45: calibration_penalty = 0.5
            elif brier_score > 0.35: calibration_penalty = 0.9
            else: calibration_penalty = 1.0
        else:
            if brier_score > 0.40: calibration_penalty = 0.5
            elif brier_score > 0.30: calibration_penalty = 0.8
            else: calibration_penalty = 1.0
        
        final_fraction = base_fraction * calibration_penalty
        
        # Apply regime-specific risk aversion penalties
        if is_capitulation_override:
            logger.info("Capitulation Override Active: Bypassing risk-off penalties and applying 0.9x guarded contrarian multiplier.")
            final_fraction *= 0.9 # Guarded contrarian Kelly
        elif is_momentum_override:
            logger.info("Momentum Ignition Active: Bypassing risk-off penalties and applying 1.25x momentum multiplier.")
            final_fraction *= 1.25 # Aggressive trend-following Kelly
                
        # Consensus Risk Modifier (Smooth Linear Scale: 0.7x to 1.2x)
        consensus_multiplier = 0.7 + (consensus_score * 0.5)
        final_fraction *= consensus_multiplier
        logger.info(f"Consensus modifier applied: {consensus_multiplier:.2f}x (score: {consensus_score})")
            
        if duration_days > half_life:
            decay_factor = math.exp(-0.2 * (duration_days - half_life))
            final_fraction *= max(0.2, decay_factor)
            
        final_fraction *= sentiment_multiplier
        
        if is_short_bet:
            final_fraction = -final_fraction
            
        return final_fraction

    def compute_multi_asset_kelly(self, mlp_predictions, dominant_state, brier_score, duration_days=0, is_capitulation_override=False, is_momentum_override=False, is_black_swan=False, is_bull_trap=False, hmm_regime="NEUTRAL_TRANSITIONAL", current_ihi=0.0, is_downtrend=False, max_kelly_cap: float = 0.60, equity_drawdown: float = 0.0, entry_score: float = 1.0):
        if not hmm_regime:
            hmm_regime = "UNKNOWN"
        raw_allocations = {}
        for asset, preds in mlp_predictions.items():
            prob = preds.get("bull_probability", 0.5)
            consensus_score = preds.get("consensus_score", 0.0)
            effective_prob = prob
            
            asset_is_bull_trap = (asset == "spx" and is_bull_trap)
            
            asset_thresholds = {
                "spx":  0.50, "btc":  0.52, "gld":  0.52, "wti":  0.54,
                "nvda": 0.53, "tsla": 0.56, "dell": 0.55, "spce": 0.72,
            }
            asset_conviction_threshold = asset_thresholds.get(asset, 0.55)
            
            is_bull_bet = prob >= 0.5
            if hmm_regime == "LIQUIDITY_DRIVEN_RALLY":
                if is_bull_bet: asset_conviction_threshold -= 0.05
                else: asset_conviction_threshold += 0.05
            elif hmm_regime in ["DEFENSIVE_RISK_OFF", "CRISIS_BEAR_MARKET"]:
                if not is_bull_bet: asset_conviction_threshold -= 0.05
                else: asset_conviction_threshold += 0.05
                
            asset_conviction_threshold = max(0.52, min(0.75, asset_conviction_threshold))
            
            raw_kelly = self.compute_kelly_sizing(
                max_prob=effective_prob, dominant_state=dominant_state, brier_score=brier_score, 
                duration_days=duration_days, is_capitulation_override=is_capitulation_override, 
                is_momentum_override=is_momentum_override, is_black_swan=is_black_swan, 
                is_bull_trap=asset_is_bull_trap, hmm_regime=hmm_regime, current_ihi=current_ihi,
                consensus_score=consensus_score, conviction_threshold=asset_conviction_threshold
            )
            raw_allocations[asset] = raw_kelly

        allocations = {}
        spx_raw = raw_allocations.get("spx", 0.0)
        allocations["SPX_Kelly"] = 0.0
        allocations["Short_Kelly"] = 0.0
        
        if spx_raw > 0:
            allocations["SPX_Kelly"] = round(min(max_kelly_cap, spx_raw), 3)
            if is_downtrend:
                allocations["SPX_Kelly"] = round(allocations["SPX_Kelly"] * 0.5, 3)
                logger.warning("SPX is in a macro downtrend. Halving long Kelly allocation.")
        elif spx_raw < -0.05:
            allocations["Short_Kelly"] = round(min(max_kelly_cap, abs(spx_raw)), 3)
            logger.info(f"Negative Edge Detected. Shorting enabled with allocation {allocations['Short_Kelly']}.")

        if is_black_swan:
            logger.error("BLACK SWAN CIRCUIT BREAKER ACTIVE: Liquidating all SPX equity exposure.")
            allocations["SPX_Kelly"] = 0.0

        for asset, raw_k in raw_allocations.items():
            if asset.lower() not in ["spx", "short"]:
                allocations[f"{asset.upper()}_Kelly"] = round(max(0.0, min(1.0, raw_k)), 3)

        spx_prob = mlp_predictions.get("spx", {}).get("bull_probability", 0.5)
        
        if dominant_state == "risk_off" or hmm_regime in ("DEFENSIVE_RISK_OFF", "VOLATILITY_EXPANSION"):
            logger.info(f"Risk-Off environment detected. Allocating proportional safe-haven diversity.")
            allocations["GLD_Kelly"] = max(allocations.get("GLD_Kelly", 0.0), 0.20)
            
        if spx_prob < 0.35:
            logger.info("Extreme Weakness: SPX collapsing. Suppressing high-beta names, boosting safe havens.")
            allocations["GLD_Kelly"] = min(1.0, round(allocations.get("GLD_Kelly", 0.0) * 1.5, 3))
            allocations["Short_Kelly"] = min(1.0, round(allocations.get("Short_Kelly", 0.0) * 1.2, 3))
            for k in list(allocations.keys()):
                if k not in ["SPX_Kelly", "Short_Kelly", "BTC_Kelly", "GLD_Kelly", "WTI_Kelly"]:
                    allocations[k] = round(allocations[k] * 0.25, 3)
            if "SPCE_Kelly" in allocations: allocations["SPCE_Kelly"] = 0.0

        if dominant_state == "risk_off" or is_black_swan:
            for k in list(allocations.keys()):
                if k not in ["SPX_Kelly", "Short_Kelly", "BTC_Kelly", "GLD_Kelly", "WTI_Kelly"]:
                    allocations[k] = 0.0
            if dominant_state == "risk_off" and "BTC_Kelly" in allocations:
                allocations["BTC_Kelly"] = round(allocations["BTC_Kelly"] * 0.30, 3)
            logger.warning(f"Regime Gate: dominant_state={dominant_state}. All single-name long equity zeroed.")

        STRESS_REGIMES = {"DEFENSIVE_RISK_OFF", "VOLATILITY_EXPANSION"}
        if any(hmm_regime.startswith(s) for s in STRESS_REGIMES):
            for k in list(allocations.keys()):
                if k not in ["SPX_Kelly", "Short_Kelly", "BTC_Kelly", "GLD_Kelly", "WTI_Kelly"]:
                    allocations[k] = 0.0
            logger.warning(f"Ensemble Coherence Gate: {hmm_regime}. Single-name equity zeroed.")

        if allocations["SPX_Kelly"] > 0.05 and dominant_state != "risk_off" and not is_black_swan:
            if not any(hmm_regime.startswith(s) for s in STRESS_REGIMES):
                if "NVDA_Kelly" in allocations: allocations["NVDA_Kelly"] = max(allocations["NVDA_Kelly"], round(allocations["SPX_Kelly"] * 0.35, 3))
                if "BTC_Kelly" in allocations: allocations["BTC_Kelly"] = max(allocations["BTC_Kelly"], round(allocations["SPX_Kelly"] * 0.25, 3))
                if "TSLA_Kelly" in allocations: allocations["TSLA_Kelly"] = max(allocations["TSLA_Kelly"], round(allocations["SPX_Kelly"] * 0.20, 3))

        entry_score_multiplier = max(0.3, min(1.0, entry_score))
        for k in allocations.keys():
            allocations[k] = round(allocations[k] * entry_score_multiplier, 3)
            
        # Apply fundamental analyst conviction
        fundamental_scores_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'state', 'fundamental_scores.json')
        if os.path.exists(fundamental_scores_path):
            try:
                import json
                with open(fundamental_scores_path, 'r') as f:
                    fundamental_data = json.load(f)
                    
                for k in list(allocations.keys()):
                    asset = k.replace("_Kelly", "").upper()
                    # The JSON uses original tickers (e.g., NVDA). 
                    # Our keys are like NVDA_Kelly
                    if asset in fundamental_data:
                        score = fundamental_data[asset].get("conviction_score", 0.0)
                        if score < -0.5:
                            allocations[k] = round(allocations[k] * 0.5, 3)
                            logger.warning(f"Fundamental Analysis for {asset} is highly negative (score: {score}). Slashing allocation by 50%.")
                        elif score > 0.5:
                            allocations[k] = min(max_kelly_cap, round(allocations[k] * 1.2, 3))
                            logger.info(f"Fundamental Analysis for {asset} is highly positive (score: {score}). Boosting allocation by 20%.")
            except Exception as e:
                logger.error(f"Failed to apply fundamental scores: {e}")
        if entry_score_multiplier < 1.0:
            logger.info(f"Entry Score Multiplier: {entry_score_multiplier:.2f} applied to Kellys.")

        total_exposure = sum(abs(v) for v in allocations.values())
        if total_exposure > 1.0:
            scale = 1.0 / total_exposure
            for k in allocations.keys():
                allocations[k] = round(allocations[k] * scale, 3)
            total_exposure = sum(abs(v) for v in allocations.values())

        allocations["Cash"] = round(1.0 - total_exposure, 3)
        return allocations
