import json
import os
from src.observability.logger import get_logger

logger = get_logger("fundamental_analyst_agent")

class AnalystAgent:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            fallback_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'api_keys.json')
            if os.path.exists(fallback_path):
                with open(fallback_path, 'r') as f:
                    self.api_key = json.load(f).get('GEMINI_API_KEY')
                    
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except ImportError:
                self.client = None
                logger.error("google.genai is not installed.")
        else:
            self.client = None
            
    def analyze(self, ticker: str, data: dict) -> dict:
        if not self.client:
            logger.warning("No Gemini client configured. Returning neutral fundamental score.")
            return {
                "conviction_score": 0.0,
                "reasoning": "Fundamental agent running in bypass mode. Assuming neutral 0.0 score.",
                "insights": {}
            }
            
        if data.get("type") != "EQUITY":
            return {
                "conviction_score": 0.0,
                "reasoning": f"{ticker} is not an equity. Fundamentals not processed.",
                "insights": {}
            }
            
        prompt = f"""You are a master institutional fundamental equity researcher.
Analyze the following financial data for {ticker}.
Based on the 7-phase equity research framework, synthesize the insights considering:
1. Value Chain & Ecosystem Moat
2. Margin Defensibility
3. Capital Allocation
4. AI/Macro Risks

Provide a raw JSON response (no markdown blocks, no ```json) containing:
- "conviction_score": A float between -1.0 (strong sell) to 1.0 (strong buy).
- "reasoning": 2-3 sentences summarizing the thesis.
- "insights": A dictionary of the 4 categories above with a 1 sentence observation for each.

Financial Data:
{json.dumps(data, indent=2)}
"""

        try:
            response = self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            raw_text = response.text.strip()
            
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].strip()
                
            result = json.loads(raw_text)
            return result
        except Exception as e:
            logger.error(f"Failed to analyze {ticker} with Gemini: {e}")
            return {
                "conviction_score": 0.0,
                "reasoning": f"Error during LLM analysis: {str(e)}",
                "insights": {}
            }
