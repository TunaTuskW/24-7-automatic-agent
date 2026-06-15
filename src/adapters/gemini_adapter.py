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
            
    def run_llm_macro(self, headlines: List[str], calendar_events: List[Any], spread_2s10s: float, vix_zscore: float, volume_heat: float, max_retries: int = 5) -> Dict[str, Any]:
        if not self.client:
            logger.warning("No Gemini client. Returning default LLM Macro response.")
            return {
                "fed_policy_hawkishness_prob": 0.5, 
                "fear_greed_sentiment_score": 0.5, 
                "credit_stress": 0.0,
                "liquidity_withdrawal": 0.0,
                "kelly_multiplier": 1.0,
                "quantitative_divergence_flag": False, 
                "reasoning": "System operating in Local Bypass Mode. LLM Macro Provider disabled or unconfigured. Assuming standard baseline environment with neutral macroeconomic stance."
            }
            
        headlines_text = "\n".join(headlines[:20])
        calendar_text = json.dumps([e.model_dump() for e in calendar_events], indent=2) if calendar_events else "No upcoming high-impact events."
        
        prompt = f"""You are the master LLM Macro Expert for a quantitative trading system. Your task is to analyze the current macroeconomic state and market psychology by synthesizing the latest financial news headlines WITH quantitative indicators (bond spreads, VIX z-score, volume heat, and economic calendar).

Output strictly valid JSON with no markdown. The JSON MUST contain exactly the following keys:
- "reasoning": A 3 to 4 sentence step-by-step synthesis explaining how the quantitative data and news justify your conclusions.
- "fed_policy_hawkishness_prob": A float between 0.0 and 1.0 (1.0 = extreme rate hike pressure).
- "fear_greed_sentiment_score": A float between 0.0 and 1.0 (1.0 = extreme greed/bullishness).
- "credit_stress": A float between 0.0 and 1.0 (1.0 = high credit stress / default fears).
- "liquidity_withdrawal": A float between 0.0 and 1.0 (1.0 = rapid liquidity draining).
- "kelly_multiplier": A float between 0.5 and 1.5. If the macro environment is dangerously toxic (e.g., credit stress + hawkishness), output 0.5 to slash risk. If it's a Goldilocks environment, output 1.2. Otherwise, 1.0.
- "quantitative_divergence_flag": A boolean. Set to true ONLY if news headlines are extremely bullish but the VIX z-score is spiking > 1.5 (indicating hidden institutional panic).

{{
  "reasoning": "string",
  "fed_policy_hawkishness_prob": 0.5,
  "fear_greed_sentiment_score": 0.5,
  "credit_stress": 0.0,
  "liquidity_withdrawal": 0.0,
  "kelly_multiplier": 1.0,
  "quantitative_divergence_flag": false
}}

Recent Headlines:
{headlines_text}

Upcoming High-Impact Calendar Events (USD, EUR, JPY):
{calendar_text}

Current 2s10s Spread: {spread_2s10s}
VIX z-score: {vix_zscore}
Volume Activity Heat: {volume_heat}"""

        import time
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception as e:
                if ("503" in str(e) or "429" in str(e)) and attempt < (max_retries - 1):
                    sleep_time = (attempt + 1) * 10
                    logger.warning(f"Provider: Gemini | API UNAVAILABLE/RATE_LIMIT. Retrying LLM Macro in {sleep_time} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Provider: Gemini | LLM Macro failed after {attempt+1} attempts: {e}")
                    
                    reasoning_text = f"Fallback to neutral. LLM Macro Provider error: {str(e)[:100]}..."
                    if "API key not valid" in str(e) or "400" in str(e) or "API_KEY_INVALID" in str(e):
                        reasoning_text = "System operating in Local Bypass Mode. Gemini API Key is missing or invalid. Assuming baseline macro environment with neutral risk sentiment."
                        
                    return {
                        "fed_policy_hawkishness_prob": 0.5, 
                        "fear_greed_sentiment_score": 0.5, 
                        "credit_stress": 0.0,
                        "liquidity_withdrawal": 0.0,
                        "kelly_multiplier": 1.0,
                        "quantitative_divergence_flag": False, 
                        "reasoning": reasoning_text
                    }
