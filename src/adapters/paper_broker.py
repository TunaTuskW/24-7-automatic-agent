import os
import csv
import json
import logging
from datetime import datetime
from src.observability.logger import get_logger

logger = get_logger(__name__)

# Add file handler for dry execution
log_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "logs", "paper_broker.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
fh = logging.FileHandler(log_path)
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - [%(name)s] %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

class PaperBroker:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        
        self.paper_trading_dir = os.path.join(data_dir, "paper_trading")
        os.makedirs(self.paper_trading_dir, exist_ok=True)
        
        self.portfolio_path = os.path.join(self.paper_trading_dir, "paper_portfolio.json")
        self.ledger_path = os.path.join(self.paper_trading_dir, "paper_ledger.csv")
        
        self.starting_cash = 10000.0
        self.slippage_pct = 0.0005 # 5 bps slippage
        self.min_trade_size = 10.0 # Minimum $10 trade
        
        self.portfolio = self._load_portfolio()
        
    def _load_portfolio(self):
        if os.path.exists(self.portfolio_path):
            with open(self.portfolio_path, 'r') as f:
                return json.load(f)
        else:
            return {
                "cash": self.starting_cash,
                "positions": {},
                "total_equity": self.starting_cash,
                "last_update": datetime.now().isoformat()
            }
            
    def _save_portfolio(self):
        self.portfolio["last_update"] = datetime.now().isoformat()
        with open(self.portfolio_path, 'w') as f:
            json.dump(self.portfolio, f, indent=4)
            
    def _log_trade(self, ticker, action, shares, price, value, fee):
        file_exists = os.path.exists(self.ledger_path)
        with open(self.ledger_path, 'a', newline='') as csvfile:
            fieldnames = ['timestamp', 'action', 'ticker', 'shares', 'price', 'value', 'fee']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
                
            writer.writerow({
                'timestamp': datetime.now().isoformat(),
                'action': action,
                'ticker': ticker,
                'shares': round(shares, 6),
                'price': round(price, 2),
                'value': round(value, 2),
                'fee': round(fee, 2)
            })

    def execute_rebalance(self, target_allocations: dict, current_prices: dict):
        """
        target_allocations: dict mapped by ticker to target fraction (e.g. {"SPX": 0.5, "Gold": 0.2})
        current_prices: dict mapped by ticker to current spot price (e.g. {"SPX": 5300.0, "Gold": 2350.0})
        """
        logger.info(f"PaperBroker starting rebalance. Targets: {target_allocations}")
        
        # 1. Compute current equity
        total_equity = self.portfolio["cash"]
        for ticker, shares in self.portfolio["positions"].items():
            if ticker in current_prices:
                total_equity += shares * current_prices[ticker]
            else:
                logger.warning(f"Price for {ticker} missing during rebalance! Using last known weight.")
                
        self.portfolio["total_equity"] = total_equity
        logger.info(f"Current Total Equity: ${total_equity:,.2f} | Cash: ${self.portfolio['cash']:,.2f}")
        
        # 2. Determine target values
        target_values = {}
        for ticker, target_frac in target_allocations.items():
            target_values[ticker] = total_equity * target_frac
            
        # Add tickers we own but aren't in target_allocations (target = 0)
        for ticker in self.portfolio["positions"].keys():
            if ticker not in target_values:
                target_values[ticker] = 0.0

        # 3. Process SELLS first (to free up cash)
        for ticker, target_val in target_values.items():
            if ticker not in current_prices:
                continue
                
            current_shares = self.portfolio["positions"].get(ticker, 0.0)
            current_val = current_shares * current_prices[ticker]
            
            diff_val = target_val - current_val
            
            # If we need to sell (diff_val is negative) and the trade size is > min_trade_size
            if diff_val < -self.min_trade_size:
                val_to_sell = abs(diff_val)
                # Apply slippage (sell at a slightly worse/lower price)
                exec_price = current_prices[ticker] * (1.0 - self.slippage_pct)
                shares_to_sell = val_to_sell / exec_price
                
                # Cap at what we actually own
                if shares_to_sell > current_shares:
                    shares_to_sell = current_shares
                    val_to_sell = shares_to_sell * exec_price
                    
                fee = val_to_sell * self.slippage_pct # Record the cost of slippage
                
                self.portfolio["positions"][ticker] -= shares_to_sell
                self.portfolio["cash"] += val_to_sell
                
                if self.portfolio["positions"][ticker] <= 1e-6:
                    del self.portfolio["positions"][ticker]
                    
                self._log_trade(ticker, "SELL", shares_to_sell, exec_price, val_to_sell, fee)
                logger.info(f"PAPER SELL: {shares_to_sell:.4f} {ticker} @ ${exec_price:.2f}")

        # 4. Process BUYS next (using freed up cash)
        for ticker, target_val in target_values.items():
            if ticker not in current_prices:
                continue
                
            current_shares = self.portfolio["positions"].get(ticker, 0.0)
            current_val = current_shares * current_prices[ticker]
            
            diff_val = target_val - current_val
            
            # If we need to buy (diff_val is positive) and trade size is > min_trade_size
            if diff_val > self.min_trade_size:
                val_to_buy = diff_val
                
                # Cap at available cash
                if val_to_buy > self.portfolio["cash"]:
                    val_to_buy = self.portfolio["cash"]
                    
                if val_to_buy > self.min_trade_size:
                    # Apply slippage (buy at a slightly worse/higher price)
                    exec_price = current_prices[ticker] * (1.0 + self.slippage_pct)
                    shares_to_buy = val_to_buy / exec_price
                    
                    fee = val_to_buy * self.slippage_pct # Record the cost of slippage
                    
                    self.portfolio["positions"][ticker] = self.portfolio["positions"].get(ticker, 0.0) + shares_to_buy
                    self.portfolio["cash"] -= val_to_buy
                    
                    self._log_trade(ticker, "BUY", shares_to_buy, exec_price, val_to_buy, fee)
                    logger.info(f"PAPER BUY: {shares_to_buy:.4f} {ticker} @ ${exec_price:.2f}")

        # 5. Final update
        self._save_portfolio()
        logger.info(f"Rebalance complete. New Equity: ${total_equity:,.2f} | Cash: ${self.portfolio['cash']:,.2f}")
