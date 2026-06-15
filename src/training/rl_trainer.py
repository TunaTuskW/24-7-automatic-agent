"""
RL Agent Training Script — run offline, quarterly.
Usage: PYTHONPATH=. python3 src/training/rl_trainer.py --interval 1d
"""
import os
import argparse
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnRewardThreshold
from src.training.rl_environment import QuantOSEnv

ASSET_RETURNS_COLS = ["spx", "short", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]

def load_training_data(interval: str = "1d") -> tuple:
    """
    Load features and returns from the existing backtester-generated data.
    
    This function calls fetch_training_data from train_models.py and extracts:
    - features_df: (T, 20) feature vectors matching ordered_feature_keys
    - returns_df:  (T, 9) 1-bar forward returns per asset
    """
    from src.training.train_models import fetch_training_data

    df = fetch_training_data(interval=interval)

    feature_cols = [
        "spx_ret", "dxy_ret", "vix_zscore", "Inst_Heat_Index", "wti_ret",
        "gsr_ret", "us10y_delta", "spread_level", "btc_ret",
        "es_ret", "nq_ret", "rty_ret", "nvda_ret", "tsla_ret", "dell_ret", "spce_ret",
        "spx_rsi_14", "spx_macd_hist", "spx_bbw", "spx_vix_corr"
    ]

    features_df = df[feature_cols].dropna()

    # Build 1-bar forward returns for each asset
    returns = pd.DataFrame(index=features_df.index)
    returns["spx"]   = df["spx_ret"].shift(-1).reindex(features_df.index)
    returns["short"] = -df["spx_ret"].shift(-1).reindex(features_df.index)  # Inverse SPX
    returns["btc"]   = df["btc_ret"].shift(-1).reindex(features_df.index)
    returns["gld"]   = df["gld_ret"].shift(-1).reindex(features_df.index)
    returns["wti"]   = df["wti_ret"].shift(-1).reindex(features_df.index)
    returns["nvda"]  = df["nvda_ret"].shift(-1).reindex(features_df.index)
    returns["tsla"]  = df["tsla_ret"].shift(-1).reindex(features_df.index)
    returns["dell"]  = df["dell_ret"].shift(-1).reindex(features_df.index)
    returns["spce"]  = df["spce_ret"].shift(-1).reindex(features_df.index)

    # Convert from percentage to decimal
    returns = (returns / 100.0).fillna(0.0)

    # Align rows only
    features_df, returns = features_df.align(returns, join="inner", axis=0)
    features_df = features_df.dropna()
    returns = returns.loc[features_df.index].fillna(0.0)

    return features_df, returns


def train_rl_agent(interval: str = "1d"):
    print(f"Loading training data for interval={interval}...")
    features_df, returns_df = load_training_data(interval)
    print(f"Training data: {len(features_df)} bars, {features_df.shape[1]} features")

    # Split: 80% train, 20% eval
    split = int(len(features_df) * 0.8)
    train_env = QuantOSEnv(features_df.iloc[:split], returns_df.iloc[:split])
    eval_env  = QuantOSEnv(features_df.iloc[split:], returns_df.iloc[split:])

    # PPO with tuned hyperparameters for financial time series
    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        verbose=1,
        policy_kwargs=dict(net_arch=[128, 64, 32])
    )

    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=f"models/rl_agent_{interval}/",
        log_path=f"data/logs/rl_training_{interval}/",
        eval_freq=5000,
        n_eval_episodes=5,
        deterministic=True
    )

    print(f"Training PPO agent for {interval}...")
    model.learn(total_timesteps=1000)

    output_path = f"models/rl_agent_{interval}/best_model.zip"
    model.save(output_path)
    print(f"Training complete. Best model saved to {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d")
    args = parser.parse_args()
    train_rl_agent(interval=args.interval)
