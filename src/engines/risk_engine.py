import numpy as np
import math
from typing import Dict, Any
from src.observability.logger import get_logger

logger = get_logger("risk-engine")

class RiskEngine:
    def run_kalman_filter(self, mcs: float, sub_components: Dict, hmm_regime_probs: Dict, prior_state=None, prior_cov=None) -> Dict[str, Any]:
        logger.info("Running Kalman Filter")
        try:
            n = 3
            x = np.array([1/3, 1/3, 1/3]) if prior_state is None else np.array([prior_state.get(k, 1/3) for k in ["risk_on", "risk_off", "transitional"]])
            P = np.eye(n) * 0.1 if prior_cov is None else np.array(prior_cov).reshape(n, n)
            Q = np.eye(n) * 0.02
            F = np.array([[0.92, 0.04, 0.04], [0.04, 0.92, 0.04], [0.04, 0.04, 0.92]])
            
            z = np.array([
                hmm_regime_probs.get("RISK_ON", 0.33),
                hmm_regime_probs.get("RISK_OFF", 0.33),
                hmm_regime_probs.get("NEUTRAL_TRANSITIONAL", 0.33)
            ])
            z /= z.sum()
            
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
            uncertainty = float(np.trace(P_updated))
            
            max_prob = float(np.max(x_updated))
            is_ambiguous = max_prob < 0.60
            
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
        except Exception as e:
            logger.error(f"Kalman filter failed: {e}")
            return {}

    def compute_shannon_entropy(self, probs: np.ndarray) -> float:
        try:
            probs = np.clip(probs, 1e-9, 1.0)
            entropy = -np.sum(probs * np.log2(probs))
            return round(float(entropy), 3)
        except Exception:
            return 1.58

    def compute_kelly_sizing(self, max_prob: float, brier_score: float, duration_days: float = 0.0, half_life: float = 99.0) -> float:
        logger.info(f"Computing Kelly size (prob: {max_prob}, brier: {brier_score})")
        edge = max_prob - 0.333
        if edge <= 0: return 0.0
        
        win_rate = max_prob
        loss_rate = 1.0 - win_rate
        base_fraction = win_rate - (loss_rate / 1.5)
        
        if brier_score > 0.25: calibration_penalty = 0.2
        elif brier_score > 0.15: calibration_penalty = 0.6
        else: calibration_penalty = 1.0
        
        final_fraction = base_fraction * calibration_penalty
        
        if duration_days > half_life:
            decay_factor = math.exp(-0.2 * (duration_days - half_life))
            final_fraction *= max(0.2, decay_factor)
            
        return round(max(0.0, min(1.0, final_fraction)), 3)
