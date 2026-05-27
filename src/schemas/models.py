from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

class NewsSignal(BaseModel):
    signal: str = Field(default="FLAT", description="Directional signal from news parsing")
    conviction: float = Field(default=0.0, description="Conviction score")
    impact: str = Field(default="Neutral Impact (Fallback)", description="Qualitative impact of the news")

class RegimeState(BaseModel):
    current: str = Field(default="UNKNOWN_TRANSITION", description="Current overarching regime")
    dominant_regime: str = Field(default="UNKNOWN_TRANSITION")
    tactical_alpha_regime: str = Field(default="UNKNOWN_TRANSITION")
    probabilities: Dict[str, float] = Field(default_factory=dict)
    tactical_alpha_probabilities: Dict[str, float] = Field(default_factory=dict)
    transition_risk: float = Field(default=0.0)
    start_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_days: float = Field(default=0.0)

class KalmanState(BaseModel):
    dominant_prob: float = Field(default=0.33)
    dominant_state: str = Field(default="UNKNOWN")
    tvd: float = Field(default=0.0)
    brier_score_calibration: float = Field(default=0.25)
    structural_ambiguity_index: float = Field(default=0.0)
    probabilities: Optional[List[float]] = Field(default=None)
    covariance_matrix: Optional[List[List[float]]] = Field(default=None)
    is_ambiguous: bool = Field(default=True)
    risk_on: float = Field(default=0.33)
    risk_off: float = Field(default=0.33)
    transitional: float = Field(default=0.33)

class MarketExtremes(BaseModel):
    temperature_zscore: float = Field(default=0.0)
    temperature_state: str = Field(default="NORMAL")
    crowded_state: str = Field(default="NORMAL")
    fragility_score: float = Field(default=0.0)
    vvix_vix_ratio: float = Field(default=0.0)

class MarketSnapshot(BaseModel):
    generated_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_indicators: Dict[str, Any] = Field(default_factory=dict)
    bonds: Dict[str, Any] = Field(default_factory=dict)
    market_extremes_insight: MarketExtremes = Field(default_factory=MarketExtremes)
    regime: RegimeState = Field(default_factory=RegimeState)
    kalman_state: KalmanState = Field(default_factory=KalmanState)
    mlp_deep_state: Dict[str, Any] = Field(default_factory=dict)
    data_science_layer: Dict[str, Any] = Field(default_factory=dict)
    mcs: Dict[str, Any] = Field(default_factory=dict)
    data_driven_escalation: str = Field(default="ROUTINE")
    news_signal: NewsSignal = Field(default_factory=NewsSignal)
