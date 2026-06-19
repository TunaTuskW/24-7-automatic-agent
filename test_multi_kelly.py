import sys
sys.path.append('.')
from src.engines.risk_engine import RiskEngine

re = RiskEngine()
mlp_preds = {
    "spx": {"bull_probability": 0.987, "consensus_score": 1.0},
    "btc": {"bull_probability": 0.987, "consensus_score": 1.0},
    "gld": {"bull_probability": 0.987, "consensus_score": 1.0},
    "wti": {"bull_probability": 0.987, "consensus_score": 1.0},
    "nvda": {"bull_probability": 0.987, "consensus_score": 1.0},
    "tsla": {"bull_probability": 0.987, "consensus_score": 1.0},
    "dell": {"bull_probability": 0.987, "consensus_score": 1.0},
    "spce": {"bull_probability": 0.987, "consensus_score": 1.0},
}
alloc = re.compute_multi_asset_kelly(
    mlp_predictions=mlp_preds,
    dominant_state="transitional",
    brier_score=0.4276,
    duration_days=5,
    is_capitulation_override=False,
    is_momentum_override=False,
    is_black_swan=False,
    is_bull_trap=False,
    hmm_regime="NEUTRAL_TRANSITIONAL_2",
    current_ihi=-0.133,
    is_downtrend=False
)
print("Allocations:", alloc)

