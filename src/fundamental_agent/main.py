import json
import os
import time
from src.observability.logger import get_logger
from src.fundamental_agent.data_fetcher import fetch_fundamentals
from src.fundamental_agent.analyst_agent import AnalystAgent

logger = get_logger("fundamental_main")

def run_fundamental_analysis():
    logger.info("Starting Deep Fundamental Equity Research...")
    
    tickers_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'tickers.json')
    if not os.path.exists(tickers_path):
        logger.error(f"Tickers config not found at {tickers_path}")
        return
        
    with open(tickers_path, 'r') as f:
        tickers = json.load(f).get("active_tickers", [])
        
    agent = AnalystAgent()
    results = {}
    
    for item in tickers:
        ticker = item.get("symbol", "")
        if not ticker: continue
        
        logger.info(f"Fetching fundamentals for {ticker}...")
        data = fetch_fundamentals(ticker)
        
        # We skip non-equities
        if data.get("type") != "EQUITY":
            logger.info(f"Skipping LLM analysis for {ticker} (Type: {data.get('type')})")
            results[ticker] = {"conviction_score": 0.0, "reasoning": "Not an equity."}
            continue
            
        logger.info(f"Synthesizing insights for {ticker} using LLM...")
        analysis = agent.analyze(ticker, data)
        results[ticker] = analysis
        
        # Sleep to avoid hitting rate limits on APIs
        time.sleep(2)
        
    # Save the results for the risk engine to consume
    state_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'state')
    os.makedirs(state_dir, exist_ok=True)
    out_path = os.path.join(state_dir, 'fundamental_scores.json')
    
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=4)
        
    logger.info(f"Fundamental Analysis complete. Saved to {out_path}")

if __name__ == "__main__":
    # In a real environment we might use APScheduler here.
    # Since we want it to run daily, we will run the analysis, then sleep for 24 hours.
    while True:
        try:
            run_fundamental_analysis()
        except Exception as e:
            logger.error(f"Error in fundamental run loop: {e}")
            
        logger.info("Fundamental subagent sleeping for 24 hours.")
        time.sleep(86400) # 24 hours
