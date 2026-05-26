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
            
            obs = np.array([features_vector])
            obs_scaled = scaler.transform(obs)
            _, posteriors = hmm.score_samples(obs_scaled)
            state_probs = posteriors[0]
            
            state_probs = np.clip(state_probs, 0.01, 0.99)
            state_probs /= state_probs.sum()
            
            regime_probs = {state_labels.get(i, f"STATE_{i}"): round(float(prob), 4) for i, prob in enumerate(state_probs)}
            dominant_state_id = int(np.argmax(state_probs))
            dominant_regime = state_labels.get(dominant_state_id, "NEUTRAL_TRANSITIONAL")
            stay_prob = float(hmm.transmat_[dominant_state_id, dominant_state_id])
            transition_risk = round(1.0 - stay_prob, 4)
            
            logger.info(f"HMM Inference complete. Dominant Regime: {dominant_regime}")
            return regime_probs, dominant_regime, transition_risk, dominant_state_id
        except Exception as e:
            logger.error(f"HMM inference failed: {e}")
            return None, None, None, None
