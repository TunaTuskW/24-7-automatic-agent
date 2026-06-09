import sys
import os
import joblib
import numpy as np

sys.path.insert(0, os.path.abspath('.'))
from src.engines.risk_engine import RiskEngine
from src.engines.feature_engine import run_mlp_inference

def run_black_swan_test():
    try:
        mlp_package = joblib.load("models/mlp_model.pkl")
    except Exception as e:
        print(f"Failed to load model: {e}")
        return
        
    risk = RiskEngine()
    
    # Normal features vector (from logs)
    features_vector = [0.18, 0.14, -0.4, -0.01, -0.17, -0.85, 0.02, 0.45, 1.07, 0.15]
    
    # Inject massive Black Swan (Crash) -> Z-score feature (index 5) = -12.0
    features_vector[5] = -12.0
    
    print("--- INJECTING -15% BLACK SWAN CRASH (-12.0 Z-Score) ---")
    
    # 1. Check Neural Network Output (Now clipped)
    features_vector_clipped = np.clip(features_vector, -4.0, 4.0).tolist()
    mlp_state = run_mlp_inference(features_vector_clipped, mlp_package, "risk_off")
    mlp_prob = mlp_state.get("bull_probability", 0.5)
    print(f"Neural Network Bull Probability (Clipped): {mlp_prob:.4f}")
    
    # 2. Check Overrides
    spx_ret_z = features_vector[5]
    ihi_val = 0.5 # Institutional volume
    is_capitulation_override = False
    if spx_ret_z < -1.5 and spx_ret_z >= -3.0 and ihi_val > 0.0 and mlp_prob > 0.5:
        is_capitulation_override = True
        
    is_black_swan = False
    if spx_ret_z < -3.5:
        is_black_swan = True
        
    print(f"Capitulation Override Active: {is_capitulation_override}")
    print(f"Black Swan Circuit Breaker Active: {is_black_swan}")
    
    # 3. Check Risk Engine Allocation
    kelly_dict = risk.compute_kelly_sizing(
        max_prob=mlp_prob,
        dominant_state="risk_off",
        brier_score=0.10, # Very confident model historically
        is_capitulation_override=is_capitulation_override,
        is_black_swan=is_black_swan,
        hmm_regime="CRISIS_DISLOCATION",
        current_ihi=0.5
    )
    
    print(f"Final SPX Kelly Exposure: {kelly_dict.get('SPX_Kelly', 0.0)}")
    print(f"Final Safe Haven Exposure: {kelly_dict.get('Safe_Haven_Kelly', 0.0)}")

if __name__ == "__main__":
    run_black_swan_test()
