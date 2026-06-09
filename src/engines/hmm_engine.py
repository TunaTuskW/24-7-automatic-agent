import numpy as np
import joblib
import os
from typing import Dict, Any, Tuple
from src.observability.logger import get_logger

logger = get_logger("hmm-engine")

class HMMEngine:
    def __init__(self, model_path: str = None):
        if not model_path:
            model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'hmm_model.pkl')
        self.hmm_package = None
        if os.path.exists(model_path):
            try:
                self.hmm_package = joblib.load(model_path)
                logger.info(f"Loaded HMM model from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load HMM model: {e}")
        else:
            logger.warning(f"HMM model not found at {model_path}")

    def run_inference(self, features_vector: list) -> Tuple[Dict, str, float, int]:
        if self.hmm_package is None:
            return None, None, None, None
        try:
            hmm = self.hmm_package["hmm"]
            scaler = self.hmm_package["scaler"]
            state_labels = self.hmm_package["state_labels"]
            
            # Force uniform start probabilities to prevent degenerate single-bar inference
            hmm.startprob_ = np.full(hmm.n_components, 1.0 / hmm.n_components)
            obs = np.array([features_vector])
            obs_scaled = scaler.transform(obs)
            _, posteriors = hmm.score_samples(obs_scaled)
            state_probs = posteriors[0]
            
            state_probs = np.clip(state_probs, 0.01, 0.99)
            state_probs /= state_probs.sum()
            
            regime_probs = {state_labels.get(i, f"STATE_{i}"): round(float(prob), 4) for i, prob in enumerate(state_probs)}
            
            # GARCH Bayesian Penalty Filter (Proxy: VIX_zscore > 1.0)
            vix_zscore = features_vector[2] if len(features_vector) > 2 else 0.0
            if vix_zscore > 1.0:
                for state in list(regime_probs.keys()):
                    if any(state.startswith(base) for base in ["RISK_ON", "LIQUIDITY"]):
                        penalty = regime_probs[state] * 0.5
                        regime_probs[state] = round(regime_probs[state] - penalty, 4)
                        neutral_key = next((k for k in regime_probs.keys() if k.startswith("NEUTRAL_TRANSITIONAL")), "NEUTRAL_TRANSITIONAL")
                        regime_probs[neutral_key] = round(regime_probs.get(neutral_key, 0.0) + penalty, 4)
                
                total = sum(regime_probs.values())
                if total > 0:
                    regime_probs = {k: round(v / total, 4) for k, v in regime_probs.items()}
            
            # Identify the new dominant regime
            dominant_regime = max(regime_probs, key=regime_probs.get)
            
            # Reverse map dominant regime to state_id for transition risk
            dominant_state_id = int(np.argmax(state_probs)) # Default fallback
            for i, label in state_labels.items():
                if label == dominant_regime:
                    dominant_state_id = i
                    break
                    
            stay_prob = float(hmm.transmat_[dominant_state_id, dominant_state_id])
            transition_risk = round(1.0 - stay_prob, 4)
            
            logger.info(f"HMM Inference complete. Dominant Regime: {dominant_regime}")
            return regime_probs, dominant_regime, transition_risk, dominant_state_id
        except Exception as e:
            logger.error(f"HMM inference failed: {e}")
            return None, None, None, None
