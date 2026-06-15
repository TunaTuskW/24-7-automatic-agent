import os
import numpy as np
from src.observability.logger import get_logger

logger = get_logger("rl-agent")

ASSET_KEYS = ["spx", "short", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]

class RLAgent:
    """
    Inference wrapper for the trained PPO policy.
    Replaces compute_multi_asset_kelly when use_rl_agent=True.
    """

    def __init__(self, interval: str = "1d"):
        self.model = None
        self.interval = interval
        model_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'models',
            f'rl_agent_{interval}', 'best_model.zip'
        )
        if os.path.exists(model_path):
            try:
                from stable_baselines3 import PPO
                self.model = PPO.load(model_path)
                logger.info(f"RL agent loaded from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load RL agent: {e}")
        else:
            logger.warning(f"RL agent model not found at {model_path}. Falling back to Kelly.")

    def is_loaded(self) -> bool:
        return self.model is not None

    def predict_allocations(
        self,
        features_vector: list,
        current_allocations: dict
    ) -> dict:
        """
        features_vector: 20-dim feature vector (same as HMM/MLP input)
        current_allocations: dict of current portfolio weights by asset name

        Returns: dict matching compute_multi_asset_kelly output format
        """
        if not self.is_loaded():
            return None

        try:
            current_alloc_vec = np.array([
                current_allocations.get(k, 0.0) for k in ASSET_KEYS
            ], dtype=np.float32)

            features_arr = np.clip(np.array(features_vector, dtype=np.float32), -4.0, 4.0)
            obs = np.concatenate([features_arr, current_alloc_vec])

            action, _ = self.model.predict(obs, deterministic=True)
            action = np.clip(action, 0.0, 1.0)

            # Normalize
            total = action.sum()
            if total > 1.0:
                action = action / total

            result = {
                "SPX_Kelly":   round(float(action[0]), 3),
                "Short_Kelly": round(float(action[1]), 3),
                "BTC_Kelly":   round(float(action[2]), 3),
                "GLD_Kelly":   round(float(action[3]), 3),
                "WTI_Kelly":   round(float(action[4]), 3),
                "NVDA_Kelly":  round(float(action[5]), 3),
                "TSLA_Kelly":  round(float(action[6]), 3),
                "DELL_Kelly":  round(float(action[7]), 3),
                "SPCE_Kelly":  round(float(action[8]), 3),
                "Cash":        round(max(0.0, 1.0 - float(action.sum())), 3)
            }

            logger.info(f"RL agent allocation: SPX={result['SPX_Kelly']}, BTC={result['BTC_Kelly']}, GLD={result['GLD_Kelly']}")
            return result

        except Exception as e:
            logger.error(f"RL agent inference failed: {e}")
            return None
