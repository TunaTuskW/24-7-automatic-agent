#!/bin/bash
export PYTHONPATH=.
echo "Training 1d models..."
python3 src/train_models.py --interval 1d
echo "Running 1d backtest..."
python3 src/quantitative_backtester.py --interval 1d
echo "Training 1h models..."
python3 src/train_models.py --interval 1h
echo "Running 1h backtest..."
python3 src/quantitative_backtester.py --interval 1h
