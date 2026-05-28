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
            
    def parse_news(self, headlines: List[str], market_data: Dict[str, float] = None) -> NewsSignal:
        if not self.client or not headlines:
            logger.warning("No Gemini client or empty headlines. Returning default news struct.")
            return NewsSignal()
            
        headlines_text = "\n".join(headlines[:20])
        market_context = json.dumps(market_data, indent=2) if market_data else "No market data provided."
        
        prompt = f"""You are a quantitative data parser. Analyze the current global macroeconomic state by synthesizing the latest financial news headlines WITH the hard quantitative market data (e.g. SPX/WTI momentum, bond yields, VIX z-scores).
Focus on Global Equity indices (SPX, Nasdaq, N225, KOSPI, Beijing/SSE, DAX), Energy/Commodity markets, and Central Bank Policy. Output strictly valid JSON with no markdown:
{{"global_macro_sentiment_score": 0.5, "fed_policy_hawkishness_prob": 0.5}}
Ensure values are floats between 0.0 and 1.0, where 1.0 sentiment is an extremely bullish global macro environment, and 1.0 hawkishness means extreme rate hike pressure.
Recent Headlines:
{headlines_text}

Current Market Data:
{market_context}"""
        
        try:
            response = self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            llm_response = json.loads(raw_text)
            
            sentiment = llm_response.get("global_macro_sentiment_score", 0.5)
            hawk_prob = llm_response.get("fed_policy_hawkishness_prob", 0.5)
            
            signal_type = "FLAT"
            impact_msg = "Routine"
            conviction = 0.0
            
            if hawk_prob > 0.75:
                signal_type = "SHORT"
                impact_msg = "RATE_SHOCK"
                conviction = hawk_prob
            elif sentiment > 0.75:
                signal_type = "LONG"
                impact_msg = "LIQUIDITY_DRIVEN_RALLY"
                conviction = sentiment
            elif sentiment < 0.25:
                signal_type = "SHORT"
                impact_msg = "GLOBAL_CONTRACTION"
                conviction = 1.0 - sentiment
                
            return NewsSignal(
                signal=signal_type,
                conviction=conviction,
                impact=impact_msg
            )
            
        except Exception as e:
            logger.error(f"LLM news processing failed: {e}")
            return NewsSignal()
