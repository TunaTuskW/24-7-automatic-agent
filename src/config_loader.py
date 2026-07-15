import os

def load_keys():
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(env_path)
    except ImportError:
        pass

    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    
    fred_path = os.path.join(config_dir, "fred_api_key.txt")
    if os.path.exists(fred_path) and not os.environ.get("FRED_API_KEY"):
        with open(fred_path, "r") as f:
            val = f.read().strip()
            if val and not val.startswith("PASTE"):
                os.environ["FRED_API_KEY"] = val
            
    gemini_path = os.path.join(config_dir, "gemini_api_key.txt")
    if os.path.exists(gemini_path) and not os.environ.get("GEMINI_API_KEY"):
        with open(gemini_path, "r") as f:
            val = f.read().strip()
            if val and not val.startswith("PASTE"):
                os.environ["GEMINI_API_KEY"] = val
            
    webhook_path = os.path.join(config_dir, "webhook_config.txt")
    if os.path.exists(webhook_path) and not os.environ.get("DISCORD_WEBHOOK_URL"):
        with open(webhook_path, "r") as f:
            val = f.read().strip()
            if val and not val.startswith("PASTE"):
                os.environ["DISCORD_WEBHOOK_URL"] = val

load_keys()
