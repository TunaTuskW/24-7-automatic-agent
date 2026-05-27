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
            
        self.api_key = None
        if os.path.exists(api_key_path):
            try:
                with open(api_key_path, 'r') as f:
                    self.api_key = json.load(f).get('GEMINI_API_KEY')
            except Exception as e:
                logger.error(f"Failed to load Gemini API key: {e}")
                
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except ImportError:
                logger.error("google.genai is not installed.")
                self.client = None
        else:
            self.client = None
            
    def parse_news(self, headlines: List[str]) -> NewsSignal:
        if not self.client or not headlines:
            logger.warning("No Gemini client or empty headlines. Returning default news struct.")
            return NewsSignal()
            
        headlines_text = "\n".join(headlines[:20])
        prompt = f"""You are a quantitative data parser. Analyze these headlines and output strictly valid JSON with no markdown:
{{"liquidity_drain_probability": 0.0, "geopolitical_shock_magnitude": 0.0}}
Ensure values are floats between 0.0 and 1.0.
Headlines:
{headlines_text}"""
        
        try:
            response = self.client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            llm_response = json.loads(raw_text)
            
            geo_mag = llm_response.get("geopolitical_shock_magnitude", 0.0)
            liq_prob = llm_response.get("liquidity_drain_probability", 0.0)
            event_flag = 1 if geo_mag > 0.7 else 0
            
            return NewsSignal(
                signal="FLAT" if event_flag == 0 else "SHORT",
                conviction=geo_mag,
                impact="Geopolitical Shock" if event_flag else "Routine"
            )
            
        except Exception as e:
            logger.error(f"LLM news processing failed: {e}")
            return NewsSignal()
