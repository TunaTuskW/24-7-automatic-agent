import sys
sys.path.append(".")
from src.quantitative_backtester import run_backtest
results, eq = run_backtest("1d")
