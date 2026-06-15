import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

class QuantOSEnv(gym.Env):
    """
    Custom Gymnasium environment wrapping the existing backtest data.
    
    State:  [20 market features] + [9 current allocation weights] = 29-dim Box
    Action: [9 target allocation weights] = 9-dim Box in [-1, 1], rescaled to [0, 1]
            (negative weights are clipped to 0 for non-short assets; short uses SPX inversion)
    Reward: 1-bar portfolio return - slippage penalty - drawdown penalty
    """

    ASSETS = ["spx", "short", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]
    SLIPPAGE_RATE = 0.001       # 10 bps
    DRAWDOWN_PENALTY = 2.0      # multiplier on drawdown penalty
    TURNOVER_PENALTY = 0.5      # multiplier on turnover penalty

    metadata = {"render_modes": []}

    def __init__(self, features_df: pd.DataFrame, returns_df: pd.DataFrame):
        """
        features_df: DataFrame of shape (T, 20) — the ordered feature vector per bar
        returns_df:  DataFrame of shape (T, 9) — 1-bar forward returns per asset per bar
                     columns: ["spx", "short", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]
        """
        super().__init__()
        self.features = features_df.values.astype(np.float32)
        self.returns  = returns_df.values.astype(np.float32)
        self.T = len(self.features)

        # Observation: 20 market features + 9 current portfolio weights
        self.observation_space = spaces.Box(
            low=-10.0, high=10.0, shape=(29,), dtype=np.float32
        )
        # Action: 9 raw weights (will be softmax-normalized to sum to 1)
        self.action_space = spaces.Box(
            low=0.0, high=1.0, shape=(9,), dtype=np.float32
        )

        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        self.equity = 1.0
        self.peak_equity = 1.0
        self.current_allocs = np.zeros(9, dtype=np.float32)
        self.current_allocs[-1] = 1.0  # Start fully in cash equivalent
        return self._obs(), {}

    def _obs(self):
        market_features = self.features[self.t]
        market_features = np.clip(market_features, -4.0, 4.0)
        return np.concatenate([market_features, self.current_allocs]).astype(np.float32)

    def step(self, action: np.ndarray):
        # Normalize action to valid allocation (sum <= 1, all >= 0)
        action = np.clip(action, 0.0, 1.0)
        total = action.sum()
        if total > 1.0:
            action = action / total
        target_allocs = action

        # Compute turnover
        turnover = float(np.sum(np.abs(target_allocs - self.current_allocs)))

        # Apply slippage cost
        slippage_cost = turnover * self.SLIPPAGE_RATE

        # Compute 1-bar return for this set of allocations
        bar_returns = self.returns[self.t]  # shape (9,)
        portfolio_return = float(np.dot(target_allocs, bar_returns))

        # Net return after slippage
        net_return = portfolio_return - slippage_cost

        # Update equity
        self.equity *= (1.0 + net_return)
        self.peak_equity = max(self.peak_equity, self.equity)
        drawdown = (self.peak_equity - self.equity) / self.peak_equity

        # Reward: net return, penalizing drawdown and excessive turnover
        reward = (net_return * 100.0) \
                 - (self.DRAWDOWN_PENALTY * max(0.0, drawdown - 0.05) * 100.0) \
                 - (self.TURNOVER_PENALTY * slippage_cost * 100.0)

        # Penalize sitting in cash too much
        cash_holding = 1.0 - total
        if cash_holding > 0.5:
            reward -= (cash_holding - 0.5) * 1.0

        # Advance
        self.current_allocs = target_allocs
        self.t += 1
        done = self.t >= self.T - 1

        info = {
            "equity": self.equity,
            "drawdown": drawdown,
            "turnover": turnover,
            "portfolio_return": portfolio_return
        }

        return self._obs(), float(reward), done, False, info

    def render(self):
        pass
