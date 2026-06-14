import os

def load_keys():
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    
    fred_path = os.path.join(config_dir, "fred_api_key.txt")
    if os.path.exists(fred_path) and not os.environ.get("FRED_API_KEY"):
        with open(fred_path, "r") as f:
            os.environ["FRED_API_KEY"] = f.read().strip()
            
    gemini_path = os.path.join(config_dir, "gemini_api_key.txt")
    if os.path.exists(gemini_path) and not os.environ.get("GEMINI_API_KEY"):
        with open(gemini_path, "r") as f:
            os.environ["GEMINI_API_KEY"] = f.read().strip()
            
    webhook_path = os.path.join(config_dir, "webhook_config.txt")
    if os.path.exists(webhook_path) and not os.environ.get("DISCORD_WEBHOOK_URL"):
        with open(webhook_path, "r") as f:
            os.environ["DISCORD_WEBHOOK_URL"] = f.read().strip()

load_keys()
