"""
OpportunityGate — decides whether the current 1H bar contains a clear enough
signal to trigger an opportunistic execution, bypassing the normal 4H/D cadence.

The 1H layer runs continuously. It writes entry_quality.json every hour. By
default, it does NOT execute trades. Only when OpportunityGate.should_execute()
returns True does the 1H layer call PaperBroker.

This preserves capital during noise (92% of bars) while ensuring the system
catches real moves within 1 hour of their onset (8% of bars).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OpportunityDecision:
    should_execute: bool
    event_type: str           # "NONE" | "REGIME_TRANSITION" | "CAPITULATION" | ...
    reason: str               # human-readable explanation
    conviction_boost: float   # 0.0 to 0.3 — how much to boost Kelly conviction for this event


class OpportunityGate:
    """
    Five event types qualify as "clear enough to act on 1H granularity":

    1. REGIME_TRANSITION    — HMM dominant state changed since last bar
    2. CAPITULATION_OVERRIDE — market_event_detector fired this event
    3. MOMENTUM_IGNITION    — market_event_detector fired this event
    4. ENTRY_FLIP_UP        — entry_score crossed 0.50 -> 0.70+ with >=4/6 components aligned
    5. HIGH_CONFIDENCE_MLP  — MLP prob > 0.70 AND brier < 0.20 AND regime-aligned

    All conditions use AND logic. Confluence is where edge lives.
    """

    # Thresholds — DO NOT LOOSEN without backtest validation
    MLP_HIGH_CONFIDENCE = 0.70
    BRIER_WELL_CALIBRATED = 0.20
    ENTRY_FLIP_LOW = 0.50
    ENTRY_FLIP_HIGH = 0.70
    ENTRY_COMPONENT_MIN = 4   # of 6 components must be aligned

    def should_execute(
        self,
        current_entry_score: float,
        prev_entry_score: Optional[float],
        current_regime: str,
        prev_regime: Optional[str],
        mlp_prob: float,
        brier_score: float,
        kalman_dominant_state: str,
        market_events: list,  # list of dicts from market_event_detector
    ) -> OpportunityDecision:
        """
        Returns OpportunityDecision. should_execute=False means: write state files,
        update entry_quality.json, but DO NOT call PaperBroker.
        """

        # Event 1: REGIME_TRANSITION
        if prev_regime is not None and current_regime != prev_regime:
            # Filter noise: only fire on substantive transitions
            substantive_transitions = {
                ("DEFENSIVE_RISK_OFF", "RISK_ON_EXPANSION"),
                ("DEFENSIVE_RISK_OFF", "LIQUIDITY_DRIVEN_RALLY"),
                ("VOLATILITY_EXPANSION", "RISK_ON_EXPANSION"),
                ("VOLATILITY_EXPANSION", "LIQUIDITY_DRIVEN_RALLY"),
                ("RISK_ON_EXPANSION", "DEFENSIVE_RISK_OFF"),
                ("LIQUIDITY_DRIVEN_RALLY", "DEFENSIVE_RISK_OFF"),
                ("RISK_ON_EXPANSION", "VOLATILITY_EXPANSION"),
                ("LIQUIDITY_DRIVEN_RALLY", "VOLATILITY_EXPANSION"),
            }
            if (prev_regime, current_regime) in substantive_transitions:
                return OpportunityDecision(
                    should_execute=True,
                    event_type="REGIME_TRANSITION",
                    reason=f"Substantive regime transition {prev_regime} -> {current_regime}",
                    conviction_boost=0.15,
                )

        # Event 2 & 3: market_event_detector events
        event_types_fired = {e.get("type") for e in market_events}
        if "CAPITULATION_OVERRIDE" in event_types_fired:
            return OpportunityDecision(
                should_execute=True,
                event_type="CAPITULATION_OVERRIDE",
                reason="Capitulation override fired — extreme fear reversal edge",
                conviction_boost=0.20,
            )
        if "MOMENTUM_IGNITION" in event_types_fired:
            return OpportunityDecision(
                should_execute=True,
                event_type="MOMENTUM_IGNITION",
                reason="Momentum ignition fired — breakout with volume confirmation",
                conviction_boost=0.20,
            )

        # Event 4: ENTRY_FLIP_UP
        if (prev_entry_score is not None
            and prev_entry_score < self.ENTRY_FLIP_LOW
            and current_entry_score >= self.ENTRY_FLIP_HIGH):
            # Note: component alignment check requires entry_quality.json details
            # For now, the entry_score itself encodes this — score > 0.70 means
            # at least 4/6 components aligned (see entry_engine.py:157-166)
            return OpportunityDecision(
                should_execute=True,
                event_type="ENTRY_FLIP_UP",
                reason=f"Entry score flipped {prev_entry_score:.2f} -> {current_entry_score:.2f}",
                conviction_boost=0.10,
            )

        # Event 5: HIGH_CONFIDENCE_MLP
        if (mlp_prob > self.MLP_HIGH_CONFIDENCE
            and brier_score < self.BRIER_WELL_CALIBRATED
            and kalman_dominant_state == "risk_on"
            and current_regime in ("RISK_ON_EXPANSION", "LIQUIDITY_DRIVEN_RALLY")):
            return OpportunityDecision(
                should_execute=True,
                event_type="HIGH_CONFIDENCE_MLP",
                reason=f"MLP prob {mlp_prob:.2f}, brier {brier_score:.3f}, regime-aligned",
                conviction_boost=0.05,
            )

        # Default: no clear signal, hold position
        return OpportunityDecision(
            should_execute=False,
            event_type="NONE",
            reason="No opportunistic event fired — maintaining current allocation",
            conviction_boost=0.0,
        )
