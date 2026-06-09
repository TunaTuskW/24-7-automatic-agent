import sys
import os

# Add src to python path
sys.path.append("/Users/mac/agent")

from src.engines.risk_engine import RiskEngine
from src.engines.feature_engine import run_self_calibration
from src.engines.consensus_engine import ConsensusEngine

def test_retail_noise_filter():
    risk_engine = RiskEngine()
    
    # Positive dominant state, positive return case but with IHI negative: SPX Kelly must be cut in half
    # Let's test compute_kelly_sizing with dominant_state = "risk_on"
    # base prob = 0.6, win_rate = 0.6, loss_rate = 0.4
    # base_fraction = 0.6 - (0.4 / 2.0) = 0.4
    # final_fraction = 0.4
    # regular Kelly sizing: spx_kelly = 0.4
    # When current_ihi < 0: spx_kelly should be cut in half to 0.2
    
    res_normal = risk_engine.compute_kelly_sizing(
        max_prob=0.6,
        dominant_state="risk_on",
        brier_score=0.10,
        current_ihi=0.5,
        hmm_regime="RISK_ON_EXPANSION"
    )
    
    res_slashed = risk_engine.compute_kelly_sizing(
        max_prob=0.6,
        dominant_state="risk_on",
        brier_score=0.10,
        current_ihi=-0.5,
        hmm_regime="RISK_ON_EXPANSION"
    )
    
    spx_normal = res_normal["SPX_Kelly"]
    spx_slashed = res_slashed["SPX_Kelly"]
    
    print(f"SPX Normal Kelly: {spx_normal}")
    print(f"SPX Slashed Kelly: {spx_slashed}")
    
    assert spx_slashed == round(spx_normal * 0.5, 3), "SPX Kelly sizing did not slash by 50% under Retail Noise Filter"
    print("SUCCESS: test_retail_noise_filter passed.")

def test_safe_haven_overlay():
    risk_engine = RiskEngine()
    
    # During CRISIS_DISLOCATION, if SPX Kelly falls below 20% (0.2), Safe Haven Overlay should scale up to 1.0 - spx_kelly
    res_normal = risk_engine.compute_kelly_sizing(
        max_prob=0.6,
        dominant_state="risk_on",
        brier_score=0.10,
        current_ihi=0.5,
        hmm_regime="CRISIS_DISLOCATION"
    )
    
    # Let's force SPX Kelly below 0.2 using negative IHI to slash SPX kelly to < 0.2 (0.4 -> 0.2, wait let's use a lower max_prob or higher brier score to make sure it's below 0.2)
    # E.g. max_prob=0.45, base_fraction = 0.45 - (0.55 / 2.0) = 0.175.
    # Slashed = 0.175 * 0.5 = 0.088 -> round(0.088, 3) = 0.088
    # Since 0.088 < 0.2 and hmm_regime is CRISIS_DISLOCATION, Safe Haven Kelly must be 1.0 - 0.088 = 0.912
    res_safe_haven = risk_engine.compute_kelly_sizing(
        max_prob=0.45,
        dominant_state="risk_on",
        brier_score=0.10,
        current_ihi=-0.5,
        hmm_regime="CRISIS_DISLOCATION"
    )
    
    spx_kelly = res_safe_haven["SPX_Kelly"]
    safe_haven_kelly = res_safe_haven["Safe_Haven_Kelly"]
    
    print(f"SPX Kelly: {spx_kelly}, Safe Haven Kelly: {safe_haven_kelly}")
    assert spx_kelly < 0.2, "SPX Kelly should be below 0.2 for Safe Haven overlay to trigger"
    assert safe_haven_kelly == round(1.0 - spx_kelly, 3), "Safe Haven Kelly did not scale to 1.0 - SPX Kelly"
    print("SUCCESS: test_safe_haven_overlay passed.")

def test_echo_chamber_discount():
    consensus_engine = ConsensusEngine()
    
    macro_res = {"fed_policy_hawkishness_prob": 0.3, "reasoning": "Dovish tone."}
    psych_res = {"fear_greed_sentiment_score": 0.8, "reasoning": "High greed."}
    
    # conviction calculation = fear_greed = 0.8
    # with echo_chamber = True, conviction should be 0.8 * 0.7 = 0.56
    sig_normal = consensus_engine.synthesize(macro_res, psych_res, "RISK_ON_EXPANSION", echo_chamber=False)
    sig_echo = consensus_engine.synthesize(macro_res, psych_res, "RISK_ON_EXPANSION", echo_chamber=True)
    
    print(f"Normal conviction: {sig_normal.conviction}")
    print(f"Echo conviction: {sig_echo.conviction}")
    
    assert sig_echo.conviction == round(sig_normal.conviction * 0.70, 3), "Echo Chamber discount of 30% not applied"
    print("SUCCESS: test_echo_chamber_discount passed.")

def test_honest_brier_score():
    # Make sure run_self_calibration calculates Brier score honestly without any Retail Noise outcome tempering.
    # If the return ret was positive (e.g. current_spx_val > spx_val_at_prediction), actual_outcome must strictly be 1 even if current_ihi is negative.
    # Let's mock a prediction history
    history = [
        {
            "predicted_risk_on": 0.8,
            "spx_val_at_prediction": 100.0,
            "target_graded": False
        }
    ]
    # Grade the prediction with a positive return but a negative IHI
    # If there was outcome tempering, actual_outcome would have been overwritten to 0.
    # Since we removed outcome tempering, actual_outcome must remain 1.
    # For a prediction of 0.8 and actual_outcome of 1:
    # squared_error = (0.8 - 1) ** 2 = 0.04
    brier, graded_history = run_self_calibration(history, current_spx_val=105.0, current_ihi=-0.5, grading_delay=0)
    
    graded_item = graded_history[0]
    print(f"Graded actual outcome: {graded_item.get('actual_outcome')}")
    print(f"Graded squared error: {graded_item.get('squared_error')}")
    print(f"Calculated Brier Score: {brier}")
    
    assert graded_item.get("actual_outcome") == 1, "Brier score calculation tempered outcome despite positive return!"
    assert abs(graded_item.get("squared_error") - 0.04) < 1e-9, "Incorrect squared error in honest Brier calibration"
    assert abs(brier - 0.04) < 1e-9, "Brier score value is incorrect"
    print("SUCCESS: test_honest_brier_score passed.")

if __name__ == "__main__":
    print("--- RUNNING QUANT REFRACTOR AUDIT ---")
    test_retail_noise_filter()
    test_safe_haven_overlay()
    test_echo_chamber_discount()
    test_honest_brier_score()
    print("--- ALL AUDIT TESTS PASSED 100% SUCCESSFULLY ---")
