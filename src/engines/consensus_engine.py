from typing import Dict, Any
from src.schemas.models import NewsSignal
from src.observability.logger import get_logger

logger = get_logger("consensus-engine")

class ConsensusEngine:
    def synthesize(self, macro_res: Dict[str, Any], psych_res: Dict[str, Any], current_regime: str, echo_chamber: bool = False) -> NewsSignal:
        try:
            hawkish_prob = macro_res.get("fed_policy_hawkishness_prob", 0.5)
            fear_greed = psych_res.get("fear_greed_sentiment_score", 0.5)
            divergence = psych_res.get("quantitative_divergence_flag", False)
            
            macro_reasoning = macro_res.get("reasoning", "")
            psych_reasoning = psych_res.get("reasoning", "")
            combined_reasoning = f"Macro Expert (Llama 3 / Groq): {macro_reasoning}\n\nPsychology Expert (Gemini): {psych_reasoning}"
            
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
            if echo_chamber:
                logger.info("LLM Echo Chamber detected: Applying 0.70x multiplier to News Conviction score.")
                final_conviction *= 0.70
                
            return NewsSignal(
                signal=signal_type,
                conviction=round(final_conviction, 3),
                impact=impact_msg,
                reasoning=combined_reasoning,
                quantitative_divergence_flag=divergence
            )
        except Exception as e:
            logger.error(f"Consensus engine failed: {e}")
            return NewsSignal()
