from typing import Dict, Any
from src.schemas.models import NewsSignal
from src.observability.logger import get_logger

logger = get_logger("consensus-engine")

class ConsensusEngine:
    def synthesize(self, llm_res: Dict[str, Any], current_regime: str) -> NewsSignal:
        try:
            hawkish_prob = llm_res.get("fed_policy_hawkishness_prob", 0.5)
            fear_greed = llm_res.get("fear_greed_sentiment_score", 0.5)
            divergence = llm_res.get("quantitative_divergence_flag", False)
            
            reasoning = llm_res.get("reasoning", "")
            if not reasoning.startswith("LLM macro:"):
                combined_reasoning = f"LLM macro: {reasoning}"
            else:
                combined_reasoning = reasoning
            
            # Base conviction calculation
            conviction = (hawkish_prob + fear_greed) / 2.0
            
            signal_type = "FLAT"
            impact_msg = "Routine"
            
            if divergence:
                signal_type = "SHORT"
                impact_msg = "QUANT_DIVERGENCE_PANIC"
                conviction = max(hawkish_prob, 1.0 - fear_greed)
            elif hawkish_prob > 0.6 and fear_greed < 0.4:
                signal_type = "SHORT"
                impact_msg = "CONSENSUS_BEARISH"
                conviction = hawkish_prob
            elif hawkish_prob < 0.4 and fear_greed > 0.6:
                signal_type = "LONG"
                impact_msg = "CONSENSUS_BULLISH"
                conviction = fear_greed
            else:
                signal_type = "MIXED"
                impact_msg = "MIXED_SIGNALS"
                conviction = (hawkish_prob + fear_greed) / 2.0
                
            final_conviction = conviction
                
            credit_stress = llm_res.get("credit_stress", 0.0)
            liquidity_withdrawal = llm_res.get("liquidity_withdrawal", 0.0)
            kelly_multiplier = llm_res.get("kelly_multiplier", 1.0)
                
            return NewsSignal(
                signal=signal_type,
                conviction=round(final_conviction, 3),
                impact=impact_msg,
                reasoning=combined_reasoning,
                quantitative_divergence_flag=divergence,
                credit_stress=credit_stress,
                liquidity_withdrawal=liquidity_withdrawal,
                kelly_multiplier=kelly_multiplier
            )
        except Exception as e:
            logger.error(f"Consensus engine failed: {e}")
            return NewsSignal()
