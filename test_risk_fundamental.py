import json
import logging
from src.engines.risk_engine import RiskEngine

logging.basicConfig(level=logging.INFO)

re = RiskEngine()

allocations = {
    "SPX_Kelly": 0.5,
    "NVDA_Kelly": 0.2,
    "SPCE_Kelly": 0.1,
    "DELL_Kelly": 0.1
}

# The risk_engine logic normally does this inside compute_multi_asset_kelly
# Let's mock a call.

mlp_predictions = {
    "spx": {"bull_probability": 0.6},
    "nvda": {"bull_probability": 0.6},
    "spce": {"bull_probability": 0.6},
    "dell": {"bull_probability": 0.6}
}

final_allocs = re.compute_multi_asset_kelly(
    mlp_predictions=mlp_predictions,
    dominant_state="risk_on",
    brier_score=0.1
)

print(json.dumps(final_allocs, indent=2))
