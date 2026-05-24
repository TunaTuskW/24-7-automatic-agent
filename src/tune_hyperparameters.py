import json
import os
from google import genai
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_api_key():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            keys = json.load(f)
            return keys.get('GEMINI_API_KEY')
    return None

def fetch_tuning_text():
    # Simulate fetching FOMC minutes or Beige Book
    return """
    The Federal Reserve noted that economic activity continued to expand at a moderate pace. 
    However, contacts across several districts reported increased uncertainty due to geopolitical tensions 
    and persistent inflation in services. Liquidity conditions remain tight as quantitative tightening continues.
    Financial markets have exhibited higher short-term volatility, suggesting a need for more agile risk management.
    """

def tune_hyperparameters():
    api_key = get_api_key()
    if not api_key:
        logging.error("GEMINI_API_KEY not found in config/api_keys.json")
        return
        
    client = genai.Client(api_key=api_key)
    
    text = fetch_tuning_text()
    
    prompt = f"""Analyze the structural macroeconomic velocity from the following FOMC/Beige Book excerpt.
Output a strict JSON configuration tuning these algorithm half-lives. Do not output any markdown formatting, just the raw JSON object:
{{"RISK_ON_HALF_LIFE_DAYS": float, "KELLY_CALIBRATION_PENALTY": float}}

Text:
{text}
"""
    
    try:
        response = client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
        # Parse JSON
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        config = json.loads(raw_text)
        
        # Save to tuning_configs.json
        config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
        os.makedirs(config_dir, exist_ok=True)
        tuning_path = os.path.join(config_dir, 'tuning_configs.json')
        
        with open(tuning_path, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info(f"Successfully tuned hyperparameters: {config}")
        
    except Exception as e:
        logging.error(f"Hyperparameter tuning failed: {e}")

if __name__ == "__main__":
    tune_hyperparameters()
