import json
import os
from typing import Dict, Any, List
from src.interfaces.llm_provider import LLMProvider
from src.schemas.models import NewsSignal
from src.observability.logger import get_logger

logger = get_logger("gemini-adapter")

class GeminiAdapter(LLMProvider):
    def __init__(self, api_key_path: str = None):
        if not api_key_path:
            api_key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'api_keys.json')
            
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key and os.path.exists(api_key_path):
            try:
                with open(api_key_path, 'r') as f:
                    self.api_key = json.load(f).get('GEMINI_API_KEY')
            except Exception as e:
                logger.error(f"Failed to load Gemini API key from json: {e}")
                
        fallback_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'gemini_api_key.txt')
        if not self.api_key and os.path.exists(fallback_path):
            try:
                with open(fallback_path, 'r') as f:
                    key = f.read().strip()
                    if key and not key.startswith("paste"):
                        self.api_key = key
            except Exception as e:
                logger.error(f"Failed to load Gemini API key from txt: {e}")
                
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except ImportError:
                logger.error("google.genai is not installed.")
                self.client = None
        else:
            self.client = None
            
    def run_macro_policy_expert(self, headlines: List[str], calendar_events: List[Any], spread_2s10s: float) -> Dict[str, Any]:
        if not self.client:
            logger.warning("No Gemini client. Returning default Macro response.")
            return {"fed_policy_hawkishness_prob": 0.5, "reasoning": "Default fallback due to missing client."}
            
        headlines_text = "\n".join(headlines[:20])
        calendar_text = json.dumps([e.model_dump() for e in calendar_events], indent=2) if calendar_events else "No upcoming high-impact events."
        
        prompt = f"""You are the Macro Policy Expert. Analyze the current global macroeconomic state by synthesizing the latest financial news headlines WITH the upcoming Forex Factory high-impact economic calendar events and the current 2s10s bond spread.
Output strictly valid JSON with no markdown. The JSON MUST begin with a "reasoning" key.
You must write exactly 3 sentences of step-by-step reasoning explaining how the quantitative data justifies your conclusion BEFORE you output the final probability score.

{{
  "reasoning": "string (exactly 3 sentences)",
  "fed_policy_hawkishness_prob": 0.5
}}

Ensure fed_policy_hawkishness_prob is a float between 0.0 and 1.0, where 1.0 means extreme rate hike pressure.

Recent Headlines:
{headlines_text}

Upcoming High-Impact Calendar Events (USD, EUR, JPY):
{calendar_text}

Current 2s10s Spread: {spread_2s10s}"""

        try:
            response = self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Macro Policy Expert failed: {e}")
            return {"fed_policy_hawkishness_prob": 0.5, "reasoning": f"Error: {e}"}

    def run_market_psychology_expert(self, headlines: List[str], vix_zscore: float, volume_heat: float) -> Dict[str, Any]:
        if not self.client:
            logger.warning("No Gemini client. Returning default Psychology response.")
            return {"fear_greed_sentiment_score": 0.5, "reasoning": "Default fallback.", "quantitative_divergence_flag": False}
            
        headlines_text = "\n".join(headlines[:20])
        
        prompt = f"""You are the Market Psychology Expert. Analyze the current global market sentiment by synthesizing the latest financial news headlines WITH the hard quantitative psychology indicators (VIX z-score and volume activity heat).
Output strictly valid JSON with no markdown. The JSON MUST begin with a "reasoning" key.
You must write exactly 3 sentences of step-by-step reasoning explaining how the quantitative data justifies your conclusion BEFORE you output the final probability score.

CRITICAL DIVERGENCE RULE: If the news headlines are extremely bullish, but the VIX z-score is spiking > 1.5 (indicating hidden institutional panic), you MUST set quantitative_divergence_flag to true.

{{
  "reasoning": "string (exactly 3 sentences)",
  "fear_greed_sentiment_score": 0.5,
  "quantitative_divergence_flag": false
}}

Ensure fear_greed_sentiment_score is a float between 0.0 and 1.0, where 1.0 is extreme greed/bullishness.

Recent Headlines:
{headlines_text}

VIX z-score: {vix_zscore}
Volume Activity Heat: {volume_heat}"""

        try:
            response = self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Market Psychology Expert failed: {e}")
            return {"fear_greed_sentiment_score": 0.5, "reasoning": f"Error: {e}", "quantitative_divergence_flag": False}
