from typing import Dict, Any
from src.schemas.models import NewsSignal
from src.observability.logger import get_logger

logger = get_logger("consensus-engine")

class ConsensusEngine:
    def synthesize(self, macro_res: Dict[str, Any], psych_res: Dict[str, Any], current_regime: str) -> NewsSignal:
        try:
            hawkish_prob = macro_res.get("fed_policy_hawkishness_prob", 0.5)
            fear_greed = psych_res.get("fear_greed_sentiment_score", 0.5)
            divergence = psych_res.get("quantitative_divergence_flag", False)
            
            macro_reasoning = macro_res.get("reasoning", "")
            psych_reasoning = psych_res.get("reasoning", "")
            combined_reasoning = f"Macro Expert: {macro_reasoning}\nPsych Expert: {psych_reasoning}"
            
            # Base conviction calculation
            conviction = (hawkish_prob + fear_greed) / 2.0
            
            signal_type = "FLAT"
            impact_msg = "Routine"
            
            if divergence:
                signal_type = "SHORT"
                impact_msg = "QUANT_DIVERGENCE_PANIC"
                conviction = max(hawkish_prob, 1.0 - fear_greed)
            elif current_regime in ["RATE_SHOCK", "STAGFLATION_STRESS"] and hawkish_prob > 0.7:
                signal_type = "SHORT"
                impact_msg = "RATE_SHOCK"
                conviction = hawkish_prob
            elif current_regime == "RISK_ON_EXPANSION" and fear_greed > 0.7:
                signal_type = "LONG"
                impact_msg = "LIQUIDITY_DRIVEN_RALLY"
                conviction = fear_greed
            elif hawkish_prob > 0.8:
                signal_type = "SHORT"
                impact_msg = "RATE_SHOCK"
                conviction = hawkish_prob
            elif fear_greed > 0.8:
                signal_type = "LONG"
                impact_msg = "EXTREME_GREED"
                conviction = fear_greed
            elif fear_greed < 0.2:
                signal_type = "SHORT"
                impact_msg = "EXTREME_FEAR"
                conviction = 1.0 - fear_greed
                
            return NewsSignal(
                signal=signal_type,
                conviction=round(conviction, 3),
                impact=impact_msg,
                reasoning=combined_reasoning,
                quantitative_divergence_flag=divergence
            )
        except Exception as e:
            logger.error(f"Consensus engine failed: {e}")
            return NewsSignal()
