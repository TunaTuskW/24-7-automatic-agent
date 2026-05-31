import json
import os
import requests
import time
from typing import Dict, Any, List
from src.interfaces.llm_provider import LLMProvider
from src.observability.logger import get_logger

logger = get_logger("groq-adapter")

class GroqAdapter(LLMProvider):
    def __init__(self, api_key_path: str = None):
        if not api_key_path:
            api_key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'api_keys.json')
            
        self.api_key = os.environ.get('GROQ_API_KEY')
        if not self.api_key and os.path.exists(api_key_path):
            try:
                with open(api_key_path, 'r') as f:
                    self.api_key = json.load(f).get('GROQ_API_KEY')
            except Exception as e:
                logger.error(f"Failed to load Groq API key from json: {e}")
                
        fallback_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'groq_api_key.txt')
        if not self.api_key and os.path.exists(fallback_path):
            try:
                with open(fallback_path, 'r') as f:
                    key = f.read().strip()
                    if key and not key.startswith("paste"):
                        self.api_key = key
            except Exception as e:
                logger.error(f"Failed to load Groq API key from txt: {e}")
                
    def _call_groq_api(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("No Groq API key available.")
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
        
    def run_macro_policy_expert(self, headlines: List[str], calendar_events: List[Any], spread_2s10s: float) -> Dict[str, Any]:
        if not self.api_key:
            logger.warning("No Groq API key. Returning default Macro response.")
            return {"fed_policy_hawkishness_prob": 0.5, "reasoning": "Default fallback due to missing key."}
            
        headlines_text = "\n".join(headlines[:20])
        calendar_text = json.dumps([e.model_dump() for e in calendar_events], indent=2) if calendar_events else "No upcoming high-impact events."
        
        prompt = f"""You are the Macro Policy Expert. Analyze the current global macroeconomic state by synthesizing the latest financial news headlines WITH the upcoming Forex Factory high-impact economic calendar events and the current 2s10s bond spread.
You MUST first write a detailed Chain of Thought analysis inside a <thinking> block.
In your <thinking> block, you must:
1. Analyze the divergence between Yields and Equities.
2. Evaluate the Volatility context.
3. Synthesize the GARCH penalty risk.
After the <thinking> block, output strictly valid JSON.

<thinking>
...your detailed step-by-step reasoning here...
</thinking>

```json
{{
  "reasoning": "A concise 3-sentence summary of your thinking.",
  "fed_policy_hawkishness_prob": 0.5
}}
```

Ensure fed_policy_hawkishness_prob is a float between 0.0 and 1.0, where 1.0 means extreme rate hike pressure.

Recent Headlines:
{headlines_text}

Upcoming High-Impact Calendar Events:
{calendar_text}

Current 2s10s Spread: {spread_2s10s}"""

        for attempt in range(10):
            try:
                raw_text = self._call_groq_api(prompt)
                
                # Extract CoT
                thinking = ""
                if "<thinking>" in raw_text and "</thinking>" in raw_text:
                    thinking = raw_text.split("<thinking>")[1].split("</thinking>")[0].strip()
                    
                # Extract JSON
                json_str = raw_text
                if "```json" in raw_text:
                    json_str = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    json_str = raw_text.split("```")[1].split("```")[0].strip()
                else:
                    # try to extract everything between { and }
                    start = raw_text.find('{')
                    end = raw_text.rfind('}')
                    if start != -1 and end != -1:
                        json_str = raw_text[start:end+1]
                        
                parsed = json.loads(json_str)
                if thinking:
                    parsed["reasoning"] = f"CoT Analysis:\n{thinking}\n\nSummary:\n{parsed.get('reasoning', '')}"
                return parsed
            except Exception as e:
                if ("503" in str(e) or "429" in str(e)) and attempt < 9:
                    sleep_time = (attempt + 1) * 10
                    logger.warning(f"API UNAVAILABLE/RATE_LIMIT. Retrying Groq Macro Expert in {sleep_time} seconds (Attempt {attempt+1}/10)...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Groq Macro Policy Expert failed: {e}")
                    return {"fed_policy_hawkishness_prob": 0.5, "reasoning": f"Error: {e}"}

    def run_market_psychology_expert(self, headlines: List[str], vix_zscore: float, volume_heat: float) -> Dict[str, Any]:
        if not self.api_key:
            return {"fear_greed_sentiment_score": 0.5, "reasoning": "Default fallback.", "quantitative_divergence_flag": False}
            
        headlines_text = "\n".join(headlines[:20])
        prompt = f"""You are the Market Psychology Expert. Analyze the current global market sentiment by synthesizing the latest financial news headlines WITH the hard quantitative psychology indicators (VIX z-score and volume activity heat).
You MUST first write a detailed Chain of Thought analysis inside a <thinking> block.
In your <thinking> block, you must:
1. Analyze the panic/greed divergence between News and Quantitative data.
2. Evaluate if institutional flow matches retail sentiment.
After the <thinking> block, output strictly valid JSON.

CRITICAL DIVERGENCE RULE: If the news headlines are extremely bullish, but the VIX z-score is spiking > 1.5 (indicating hidden institutional panic), you MUST set quantitative_divergence_flag to true.

<thinking>
...your detailed step-by-step reasoning here...
</thinking>

```json
{{
  "reasoning": "A concise 3-sentence summary of your thinking.",
  "fear_greed_sentiment_score": 0.5,
  "quantitative_divergence_flag": false
}}
```

Recent Headlines:
{headlines_text}

VIX z-score: {vix_zscore}
Volume Activity Heat: {volume_heat}"""

        for attempt in range(10):
            try:
                raw_text = self._call_groq_api(prompt)
                
                # Extract CoT
                thinking = ""
                if "<thinking>" in raw_text and "</thinking>" in raw_text:
                    thinking = raw_text.split("<thinking>")[1].split("</thinking>")[0].strip()
                    
                # Extract JSON
                json_str = raw_text
                if "```json" in raw_text:
                    json_str = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    json_str = raw_text.split("```")[1].split("```")[0].strip()
                else:
                    start = raw_text.find('{')
                    end = raw_text.rfind('}')
                    if start != -1 and end != -1:
                        json_str = raw_text[start:end+1]
                        
                parsed = json.loads(json_str)
                if thinking:
                    parsed["reasoning"] = f"CoT Analysis:\n{thinking}\n\nSummary:\n{parsed.get('reasoning', '')}"
                return parsed
            except Exception as e:
                if ("503" in str(e) or "429" in str(e)) and attempt < 9:
                    sleep_time = (attempt + 1) * 10
                    logger.warning(f"API UNAVAILABLE. Retrying Groq Psych Expert in {sleep_time} seconds (Attempt {attempt+1}/10)...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Groq Market Psychology Expert failed: {e}")
                    return {"fear_greed_sentiment_score": 0.5, "reasoning": f"Error: {e}", "quantitative_divergence_flag": False}
