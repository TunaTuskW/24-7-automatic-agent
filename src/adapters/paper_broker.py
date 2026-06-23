import os
import csv
import json
import logging
import requests
from datetime import datetime
from src.observability.logger import get_logger
from src.push_to_discord import get_webhook_url, post_with_retry

logger = get_logger(__name__)

# Add file handler for dry execution
try:
    log_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "logs", "paper_broker.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - [%(name)s] %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
except Exception as e:
    logger.warning(f"Could not setup FileHandler for paper_broker (read-only FS?): {e}")

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
        self.rebalance_drift_threshold = 0.025 # 2.5% drift threshold
        
        self.portfolio = self._load_portfolio()
        
    def _load_portfolio(self):
        if os.path.exists(self.portfolio_path):
            with open(self.portfolio_path, 'r') as f:
                return json.load(f)
        else:
            return {
                "cash": self.starting_cash,
                "positions": {},
                "position_details": {},
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

    def _send_discord_alert(self, action, ticker, shares, price, total_equity, reason="Rebalancing to match new target allocations."):
        webhook_url = get_webhook_url()
        if not webhook_url:
            return
            
        color = 0x2ECC71 if action == "BUY" else 0xE74C3C
        
        embed = {
            "title": "🚨 AI Trade Execution",
            "color": color,
            "fields": [
                {
                    "name": "Action",
                    "value": f"{action} {shares:.4f} {ticker} @ ${price:.2f}",
                    "inline": False
                },
                {
                    "name": "Reasoning",
                    "value": reason,
                    "inline": False
                },
                {
                    "name": "Total Equity",
                    "value": f"${total_equity:,.2f}",
                    "inline": False
                }
            ]
        }
        
        try:
            post_with_retry(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            logger.error(f"Failed to push trade alert to Discord: {e}")

    def get_equity_drawdown(self) -> float:
        """Calculate the current drawdown from peak equity to adjust risk."""
        current_eq = self.portfolio.get("total_equity", self.starting_cash)
        peak_eq = self.portfolio.get("peak_equity", self.starting_cash)
        
        # Update peak equity in-memory only (avoid race conditions & excessive IO)
        if current_eq > peak_eq:
            self.portfolio["peak_equity"] = current_eq
            peak_eq = current_eq
            self._save_portfolio()
            
        if peak_eq > 0:
            return (peak_eq - current_eq) / peak_eq
        return 0.0

    def execute_rebalance(self, target_allocations: dict, current_prices: dict, vix_zscore: float = 0.0, hmm_regime: str = "NEUTRAL"):
        """
        target_allocations: dict mapped by ticker to target fraction (e.g. {"SPX": 0.5, "Gold": 0.2})
        current_prices: dict mapped by ticker to current spot price (e.g. {"SPX": 5300.0, "Gold": 2350.0})
        """
        logger.info(f"PaperBroker starting rebalance. Targets: {target_allocations}")
        
        # Calculate dynamic slippage based on VIX z-score
        # Base: 5 bps. Max: 50 bps. If VIX is +3 z-scores, slippage becomes ~11 bps.
        dynamic_slippage = min(0.005, max(0.0005, 0.0005 + (vix_zscore * 0.0002)))
        logger.info(f"Applied dynamic slippage: {dynamic_slippage:.4f} (VIX Z: {vix_zscore})")
        
        if "position_details" not in self.portfolio:
            self.portfolio["position_details"] = {}
        
        # 1. Compute current equity & update high watermarks
        total_equity = self.portfolio["cash"]
        for ticker, shares in self.portfolio["positions"].items():
            spot = current_prices.get(ticker)
            if spot is None or spot <= 0.0:
                # Fallback to last known peak_price to prevent $0.0 equity wipeout
                spot = self.portfolio.get("position_details", {}).get(ticker, {}).get("peak_price", 0.0)
                logger.warning(f"Price for {ticker} missing or zero during rebalance! Falling back to last known price: {spot}")

            total_equity += shares * spot
            
            if spot > 0:
                # Update high watermark for trailing stop
                if ticker not in self.portfolio["position_details"]:
                    self.portfolio["position_details"][ticker] = {"peak_price": spot}
                else:
                    self.portfolio["position_details"][ticker]["peak_price"] = max(
                        self.portfolio["position_details"][ticker].get("peak_price", spot), spot
                    )
                
        self.portfolio["total_equity"] = total_equity
        logger.info(f"Current Total Equity: ${total_equity:,.2f} | Cash: ${self.portfolio['cash']:,.2f}")
        
        # 2. Determine target values and reasons
        target_values = {}
        trade_reasons = {}
        for ticker in list(target_allocations.keys()):
            target_frac = target_allocations[ticker]
            spot = current_prices.get(ticker)
            if spot is None or spot <= 0.0:
                target_allocations[ticker] = 0.0
                target_values[ticker] = 0.0
                continue
            target_values[ticker] = total_equity * target_frac
            
        # Add tickers we own but aren't in target_allocations (target = 0)
        for ticker in list(self.portfolio["positions"].keys()):
            if ticker not in target_values:
                target_values[ticker] = 0.0
                
            # Dynamic Trailing Stop Logic (Check if we need to force 0.0 allocation)
            spot = current_prices.get(ticker)
            if spot is not None and spot > 0 and target_values[ticker] > 0.0:
                peak = self.portfolio["position_details"].get(ticker, {}).get("peak_price", spot)
                drawdown = (peak - spot) / peak if peak > 0 else 0.0
                
                # Tighten stops if regime is risk-off
                stop_threshold = 0.05 # 5% trailing stop base
                if hmm_regime.startswith("RISK_OFF") or hmm_regime == "STAGFLATION_STRESS":
                    stop_threshold = 0.03 # Tighten to 3%
                    
                if drawdown >= stop_threshold:
                    logger.warning(f"TRAILING STOP TRIGGERED for {ticker}: Drawdown {drawdown:.2%} >= limit {stop_threshold:.2%} (Peak: {peak}, Spot: {spot}). Forcing liquidation.")
                    target_values[ticker] = 0.0
                    target_allocations[ticker] = 0.0
                    trade_reasons[ticker] = f"Trailing stop triggered (Drawdown: {drawdown:.2%} >= Limit: {stop_threshold:.2%}). Liquidating."

        # 3. Process SELLS first (to free up cash)
        for ticker, target_val in target_values.items():
            spot = current_prices.get(ticker)
            if spot is None or spot <= 0.0:
                continue
                
            current_shares = self.portfolio["positions"].get(ticker, 0.0)
            current_val = current_shares * spot
            
            diff_val = target_val - current_val
            drift_pct = abs(diff_val) / total_equity if total_equity > 0 else 0.0
            
            # If we need to sell (diff_val is negative) and the drift exceeds threshold
            if diff_val < -self.min_trade_size and drift_pct >= self.rebalance_drift_threshold:
                val_to_sell = abs(diff_val)
                # Apply slippage (sell at a slightly worse/lower price)
                exec_price = spot * (1.0 - dynamic_slippage)
                shares_to_sell = val_to_sell / exec_price
                
                # Cap at what we actually own
                if shares_to_sell > current_shares:
                    shares_to_sell = current_shares
                    val_to_sell = shares_to_sell * exec_price
                    
                fee = val_to_sell * dynamic_slippage # Record the cost of slippage
                
                self.portfolio["positions"][ticker] -= shares_to_sell
                self.portfolio["cash"] += val_to_sell
                
                if self.portfolio["positions"][ticker] <= 1e-6:
                    del self.portfolio["positions"][ticker]
                    if ticker in self.portfolio.get("position_details", {}):
                        del self.portfolio["position_details"][ticker]
                    
                self._log_trade(ticker, "SELL", shares_to_sell, exec_price, val_to_sell, fee)
                logger.info(f"PAPER SELL: {shares_to_sell:.4f} {ticker} @ ${exec_price:.2f}")
                reason = trade_reasons.get(ticker, f"Rebalancing to match optimal targets for {hmm_regime.replace('_', ' ').title()} regime.")
                self._send_discord_alert("SELL", ticker, shares_to_sell, exec_price, total_equity, reason)

        # Recompute equity after sells to avoid allocating based on pre-slippage inflated equity
        total_equity = self.portfolio["cash"] + sum(
            shares * current_prices.get(t, 0) for t, shares in self.portfolio["positions"].items()
        )
        self.portfolio["total_equity"] = total_equity

        # 4. Process BUYS next (using freed up cash)
        for ticker, target_frac in target_allocations.items():
            target_val = total_equity * target_frac
            spot = current_prices.get(ticker)
            if spot is None or spot <= 0.0:
                continue
                
            current_shares = self.portfolio["positions"].get(ticker, 0.0)
            current_val = current_shares * spot
            
            diff_val = target_val - current_val
            drift_pct = abs(diff_val) / total_equity if total_equity > 0 else 0.0
            
            # If we need to buy (diff_val is positive) and drift exceeds threshold
            if diff_val > self.min_trade_size and drift_pct >= self.rebalance_drift_threshold:
                val_to_buy = diff_val
                
                # Cap at available cash
                if val_to_buy > self.portfolio["cash"]:
                    val_to_buy = self.portfolio["cash"]
                    
                if val_to_buy > self.min_trade_size:
                    # Apply slippage (buy at a slightly worse/higher price)
                    exec_price = spot * (1.0 + dynamic_slippage)
                    shares_to_buy = val_to_buy / exec_price
                    
                    fee = val_to_buy * dynamic_slippage # Record the cost of slippage
                    
                    self.portfolio["positions"][ticker] = self.portfolio["positions"].get(ticker, 0.0) + shares_to_buy
                    
                    # Initialize peak price for new buys
                    if ticker not in self.portfolio.get("position_details", {}):
                        self.portfolio["position_details"][ticker] = {"peak_price": exec_price}
                    self.portfolio["cash"] -= val_to_buy
                    
                    self._log_trade(ticker, "BUY", shares_to_buy, exec_price, val_to_buy, fee)
                    logger.info(f"PAPER BUY: {shares_to_buy:.4f} {ticker} @ ${exec_price:.2f}")
                    reason = trade_reasons.get(ticker, f"Rebalancing to match optimal targets for {hmm_regime.replace('_', ' ').title()} regime.")
                    self._send_discord_alert("BUY", ticker, shares_to_buy, exec_price, total_equity, reason)

        # 5. Final update
        self._save_portfolio()
        logger.info(f"Rebalance complete. New Equity: ${total_equity:,.2f} | Cash: ${self.portfolio['cash']:,.2f}")
