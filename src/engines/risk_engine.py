import numpy as np
import math
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
            risk_off_states = ["STAGFLATION_STRESS", "RATE_SHOCK", "DEFLATION_FEAR", "CRISIS_DISLOCATION", "COMMODITY_SHOCK", "VOLATILITY_EXPANSION"]
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

    def compute_kelly_sizing(self, max_prob: float, dominant_state: str, brier_score: float, duration_days: float = 0.0, half_life: float = 99.0, sentiment_multiplier: float = 1.0) -> float:
        logger.info(f"Computing Kelly size (prob: {max_prob}, state: {dominant_state}, brier: {brier_score})")
        
        # Base probability threshold (need at least 33% win rate expectation to play)
        edge = max_prob - 0.333
        if edge <= 0: return 0.0
        
        win_rate = max_prob
        loss_rate = 1.0 - win_rate
        base_fraction = win_rate - (loss_rate / 1.5)
        
        if brier_score > 0.25: calibration_penalty = 0.2
        elif brier_score > 0.15: calibration_penalty = 0.6
        else: calibration_penalty = 1.0
        
        final_fraction = base_fraction * calibration_penalty
        
        # Apply regime-specific risk aversion penalties
        if dominant_state == "risk_off":
            final_fraction *= 0.5  # Half-Kelly for high volatility/stress regimes
        elif dominant_state == "transitional":
            final_fraction *= 0.75 # Discounted Kelly for uncertain regimes
            
        if duration_days > half_life:
            decay_factor = math.exp(-0.2 * (duration_days - half_life))
            final_fraction *= max(0.2, decay_factor)
            
        final_fraction *= sentiment_multiplier
            
        return round(max(0.0, min(1.2, final_fraction)), 3)
