# Macro Briefing Agent v5.2.0: Paper Trading & 14-Feature Space Manual

This manual details the upgrades in **v5.2.0 (Multi-Asset Ensemble OS with Paper Trading & 14-Feature Space)**, introducing paper trading simulations, a 14-dimensional feature space, sub-directory data organization, hourly briefing pipelines, and excel/chart performance dashboards.

---

## 1. Modular Pipeline & Directory Layout Reorganization

Following the v5.2.0 upgrades, the system data files are organized into dedicated subdirectories to secure active state matrices and execution logs:

* **`data/state/`**: Holds validations snapshots and priors (`market_snapshot.json`, `market_snapshot_prior.json`).
* **`data/predictions/`**: Holds forecasts history calibration logs (`mlp_predictions_history_{interval}.json`).
* **`data/telemetry/`**: Holds real-time telemetry metrics (`live_telemetry.json`).
* **`data/paper_trading/`**: Holds the paper broker portfolios and csv ledgers (`paper_portfolio.json`, `paper_ledger.csv`).
* **`reports/`**: Holds backtest summaries, Excel trade ledgers (`paper_trading_performance.xlsx`), and visual dashboards (`paper_trading_performance.png`).

---

## 2. Expanded 14-Feature Space

The statistical z-score and HMM features vector has expanded from **10 to 14 dimensions** to incorporate futures returns across all four main US indices and raw percentage shifts in place of price anomalies:

1. **`spx_ret`**: S&P 500 Close percentage return (`delta_pct`)
2. **`dxy_ret`**: US Dollar Index percentage return (`delta_pct`)
3. **`vix_zscore`**: CBOE VIX Index z-score (`z_score`)
4. **`Inst_Heat_Index`**: Institutional Heat Index (`institutional_heat_index`)
5. **`wti_ret`**: WTI Crude Oil percentage return (`delta_pct`)
6. **`gsr_ret`**: Gold-to-Silver ratio percentage return (`delta_pct`)
7. **`us10y_delta`**: 10-year US Treasury yield daily change (`delta`)
8. **`spread_level`**: 2s10s yield spread (`spread_2s10s`)
9. **`btc_ret`**: Bitcoin percentage return (`delta_pct`)
10. **`usdcad_ret`**: USDCAD forex percentage return (`delta_pct`)
11. **`es_ret`**: S&P 500 futures percentage return (`delta_pct` of `ES=F`)
12. **`nq_ret`**: Nasdaq 100 futures percentage return (`delta_pct` of `NQ=F`)
13. **`ym_ret`**: Dow Jones futures percentage return (`delta_pct` of `YM=F`)
14. **`rty_ret`**: Russell 2000 futures percentage return (`delta_pct` of `RTY=F`)

This expanded feature vector is aligned across data adapters, HMM/Ensemble training pipelines, the central conductor, and backtesting engines.

---

## 3. Paper Trading Simulation Engine

The orchestrator integrates a simulated **Paper Broker** (`src/adapters/paper_broker.py`) to execute target asset allocations under market conditions:

* **Slippage and Fees:** Applies a default **5 bps (0.05%) slippage penalty** per execution to simulate transaction costs.
* **Minimum Trade Size:** Enforces a **$10 minimum trade threshold** to block tiny, high-frequency rebalance orders.
* **Order Sequencing:** Executes all SELL orders first to free up cash, followed by BUY orders.
* **Automated Rebalancing:** At the end of every conductor run, target Kelly allocations for SPX (`SPX_Kelly`) and Gold (`Safe_Haven_Kelly`) are queried against current spot prices and rebalanced automatically.
* **Ledger Auditing:** Appends every execution transaction to `data/paper_trading/paper_ledger.csv`.
* **Discord Execution Alerts:** Automatically posts embedded transaction alerts (BUY/SELL action details, execution price, shares, and final total portfolio equity value) directly to Discord webhooks upon trade execution.

---

## 4. Hourly Briefing Pipeline (`run_1h.sh`)

An automated bash script integrates a high-frequency **1-hour briefing update**:
1. Queries market data feeds on a `1h` (hourly) interval.
2. Compiles model consensus and voting matrices.
3. Rebalances the paper portfolio and writes transaction records.
4. Plots performance dashboards and generates XLSX spreadsheets.
5. Pushes minimalist Brutalist Markdown briefings to Discord webhook channels. Filename patterns (`1 hour update (*).md`) are explicitly supported by pattern matching in `src/push_to_discord.py` to allow hourly report dispatch.

---

## 5. Excel Dashboard & Visual Performance Analysis

A dedicated visualizer script (`src/visualize_paper_trading.py`) builds performance audit files:
* **`reports/paper_trading_performance.png`**: Draws a three-panel dashboard plotting:
  - BUY/SELL trade action scatter markers overlaying price trajectories.
  - Friction analysis mapping cumulative slippage fees paid over time.
  - performance curves tracking Realized, Unrealized, and Net portfolio PnL.
* **`reports/paper_trading_performance.xlsx`**: Exports a dual-sheet Excel spreadsheet containing:
  - **Trade Ledger**: Full chronological execution details.
  - **Performance Summary**: Compiling total trades, slippage fees paid, gross value traded, net PnL, and final equity.
