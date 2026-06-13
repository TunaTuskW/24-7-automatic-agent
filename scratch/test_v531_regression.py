import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engines.risk_engine import RiskEngine
from src.engines.feature_engine import run_self_calibration

def test_macro_trend_override():
    risk = RiskEngine()
    mlp_preds = {
        "spx": {"bull_probability": 0.9, "consensus_score": 1.0}
    }
    
    # is_downtrend = False
    kelly_false = risk.compute_multi_asset_kelly(
        mlp_predictions=mlp_preds,
        dominant_state="risk_on",
        brier_score=0.10,
        hmm_regime="RISK_ON_EXPANSION",
        is_downtrend=False
    )
    
    # is_downtrend = True
    kelly_true = risk.compute_multi_asset_kelly(
        mlp_predictions=mlp_preds,
        dominant_state="risk_on",
        brier_score=0.10,
        hmm_regime="RISK_ON_EXPANSION",
        is_downtrend=True
    )
    
    print("Test 1: Macro Trend Override (is_downtrend)")
    print(f"SPX_Kelly (is_downtrend=False): {kelly_false.get('SPX_Kelly')}")
    print(f"SPX_Kelly (is_downtrend=True):  {kelly_true.get('SPX_Kelly')}")
    assert kelly_true.get("SPX_Kelly") == 0.0, "is_downtrend did not override SPX Kelly to 0.0"

def test_consensus_modifier():
    risk = RiskEngine()
    
    # We will just test the scalar compute_kelly_sizing function directly
    kelly_low_consensus = risk.compute_kelly_sizing(
        max_prob=0.8,
        dominant_state="risk_on",
        brier_score=0.10,
        consensus_score=0.0
    )
    
    kelly_high_consensus = risk.compute_kelly_sizing(
        max_prob=0.8,
        dominant_state="risk_on",
        brier_score=0.10,
        consensus_score=1.0
    )
    
    print("\nTest 2: Consensus Modifier")
    print(f"Kelly (consensus=0.0): {kelly_low_consensus}")
    print(f"Kelly (consensus=1.0): {kelly_high_consensus}")
    assert kelly_high_consensus > kelly_low_consensus, "High consensus did not boost allocation"

def test_self_calibration():
    # history with grading_delay = 2 for testing
    history = [
        {"predicted_risk_on": 0.9, "spx_val_at_prediction": 100.0, "spx_vals_window": [101.0, 102.0], "target_graded": False},
        {"predicted_risk_on": 0.8, "spx_val_at_prediction": 101.0, "spx_vals_window": [102.0], "target_graded": False},
        {"predicted_risk_on": 0.6, "spx_val_at_prediction": 102.0, "target_graded": False}
    ]
    
    # Now simulate current day, SPX hits 103.0
    # grading_delay = 2 means the first one should be graded
    brier, updated_history = run_self_calibration(history, current_spx_val=103.0, current_ihi=0.0, grading_delay=2, interval="1d")
    
    print("\nTest 3: Self Calibration rolling returns")
    print(f"Brier Score: {brier}")
    print(f"Graded forecast actual outcome: {updated_history[0].get('actual_outcome')}")
    assert updated_history[0].get("target_graded") == True, "Forecast was not graded"
    assert len(updated_history[0]["spx_vals_window"]) == 3, "spx_vals_window did not accumulate"

if __name__ == "__main__":
    print("=== Running Regression Suite ===")
    test_macro_trend_override()
    test_consensus_modifier()
    test_self_calibration()
    print("\n✅ All tests passed!")
