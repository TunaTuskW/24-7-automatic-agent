from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

class EconomicEvent(BaseModel):
    title: str = Field(default="")
    country: str = Field(default="")
    date: str = Field(default="")
    impact: str = Field(default="High")
    forecast: str = Field(default="")
    previous: str = Field(default="")

class EconomicCalendar(BaseModel):
    events: List[EconomicEvent] = Field(default_factory=list)

class NewsSignal(BaseModel):
    signal: str = Field(default="FLAT", description="Directional signal from news parsing")
    conviction: float = Field(default=0.0, description="Conviction score")
    impact: str = Field(default="Neutral Impact (Fallback)", description="Qualitative impact of the news")
    reasoning: str = Field(default="", description="Chain-of-Thought reasoning from the LLM")
    quantitative_divergence_flag: bool = Field(default=False, description="Flag indicating narrative diverges from quantitative reality")

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

class SMCState(BaseModel):
    bos_direction: int = Field(default=0)
    choch_detected: bool = Field(default=False)
    active_ob_bullish: float = Field(default=0.0)
    active_ob_bearish: float = Field(default=0.0)
    fvg_bullish_active: bool = Field(default=False)
    fvg_bearish_active: bool = Field(default=False)
    liquidity_swept_low: bool = Field(default=False)
    liquidity_swept_high: bool = Field(default=False)
    premium_discount: str = Field(default="EQUILIBRIUM")
    smc_bias: int = Field(default=0)

class SessionState(BaseModel):
    current_session: str = Field(default="UNKNOWN")
    session_bias: str = Field(default="AVOID")
    asia_high: float = Field(default=0.0)
    asia_low: float = Field(default=0.0)
    london_swept_asia_high: bool = Field(default=False)
    london_swept_asia_low: bool = Field(default=False)
    favorable_for_entry: bool = Field(default=False)
    orb_signal: int = Field(default=0)
    orb_strength: float = Field(default=0.0)
    td9_exhaustion: bool = Field(default=False)
    td9_direction: int = Field(default=0)
    td9_count: int = Field(default=0)
    td9_perfected: bool = Field(default=False)

class LiquidityState(BaseModel):
    nearest_pool_above: float = Field(default=0.0)
    nearest_pool_below: float = Field(default=0.0)
    magnet_target: str = Field(default="NONE")
    pool_strength_above: int = Field(default=0)
    pool_strength_below: int = Field(default=0)

class TrendState(BaseModel):
    trend_state: str = Field(default="UNKNOWN")
    trend_conviction: float = Field(default=0.0)
    fast_signal: int = Field(default=0)
    slow_signal: int = Field(default=0)
    atr_stop_fast: float = Field(default=0.0)

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
    economic_calendar: EconomicCalendar = Field(default_factory=EconomicCalendar)
    smc_state: SMCState = Field(default_factory=SMCState)
    session_state: SessionState = Field(default_factory=SessionState)
    liquidity_state: LiquidityState = Field(default_factory=LiquidityState)
    trend_state: TrendState = Field(default_factory=TrendState)

class TradeRecommendation(BaseModel):
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    regime: str = Field(default="UNKNOWN")
    regime_confidence: float = Field(default=0.0)
    entry_score: float = Field(default=0.0)
    entry_bias: str = Field(default="FLAT")
    kelly_fraction: float = Field(default=0.0)
    conviction_gate_passed: bool = Field(default=False)
    macro_signal: str = Field(default="FLAT")
    macro_conviction: float = Field(default=0.0)
    signal_conflict: bool = Field(default=False)
    conflict_detail: str = Field(default="")
    recommended_action: str = Field(default="HOLD")
    recommended_allocations: Dict[str, float] = Field(default_factory=dict)
    decision_rationale: str = Field(default="")
    risk_flags: List[str] = Field(default_factory=list)
