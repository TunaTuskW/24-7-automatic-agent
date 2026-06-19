import sys
sys.path.append('.')
from src.engines.risk_engine import RiskEngine

re = RiskEngine()
raw_kelly = re.compute_kelly_sizing(
    max_prob=0.68,
    dominant_state="transitional",
    brier_score=0.4276,
    duration_days=5,
    is_capitulation_override=False,
    is_momentum_override=False,
    is_black_swan=False,
    is_bull_trap=False,
    hmm_regime="NEUTRAL_TRANSITIONAL_2",
    current_ihi=-0.133,
    consensus_score=1.0,
    conviction_threshold=0.58
)
print("Raw Kelly:", raw_kelly)

