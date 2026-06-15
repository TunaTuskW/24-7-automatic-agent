import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import json
import warnings
import argparse
import os
warnings.filterwarnings("ignore")

from src.engines.hmm_engine import HMMEngine
from src.engines.risk_engine import RiskEngine
from src.engines.feature_engine import ALL_YF_TICKERS, compute_stats, compute_volume_heat, load_mlp_models, run_multi_mlp_inference, run_self_calibration
from src.engines.rl_agent import RLAgent

def run_backtest(interval="1d", use_rl_agent=False, start_date: str = None, end_date: str = None):
    print(f"=== Starting Dynamic Quantitative Backtest ({interval}) | RL Agent: {use_rl_agent} ===")
    
    from datetime import datetime, timedelta
    _today = datetime.today()

    if start_date:
        q1_start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        q1_start = datetime(_today.year, 1, 1)

    if end_date:
        q1_end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        q1_end = _today - timedelta(days=5)

    # 90-day warmup window before start to allow rolling statistics to stabilise
    start_fetch_date = (q1_start - timedelta(days=90)).strftime("%Y-%m-%d")
    end_fetch_date = q1_end.strftime("%Y-%m-%d")
    
    tickers_to_fetch = list(ALL_YF_TICKERS.values()) + ["^TNX", "^FVX"]
    
    print(f"Downloading historical data from {start_fetch_date} to {end_fetch_date}...")
    try:
        raw_data = yf.download(tickers_to_fetch, start=start_fetch_date, end=end_fetch_date, interval=interval, group_by="ticker", progress=False, threads=True)
    except Exception as e:
        print(f"Failed to download data: {e}")
        return

    # Extract SPX Trading days in Q1
    raw_data.index = raw_data.index.tz_localize(None)
    spx_data = raw_data["^GSPC"].dropna()
    
    # Calculate Macro Trend Filter (dynamic EMA span based on interval)
    ema_span = 20
    if interval == "1h":
        ema_span = 140
    elif interval == "4h":
        ema_span = 40
    spx_ema = spx_data["Close"].ewm(span=ema_span, adjust=False).mean()
    
    q1_trading_days = spx_data[(spx_data.index >= q1_start) & (spx_data.index <= q1_end)].index

    
    hmm_model_path = os.path.join(os.path.dirname(__file__), '..', 'models', f'hmm_model_{interval}.pkl')
    # Backward compatibility fallback
    if not os.path.exists(hmm_model_path) and interval == "1d":
        hmm_model_path = None # HMMEngine will fallback to hmm_model.pkl
        
    hmm = HMMEngine(model_path=hmm_model_path)
    risk = RiskEngine()
    mlp_packages_dict = load_mlp_models(interval)
    
    prior_k_state = None
    prior_k_cov = None
    
    rl_agent_instance = None
    if use_rl_agent:
        rl_agent_instance = RLAgent(interval=interval)
    
    predictions_history = []
    dynamic_brier_score = 0.15
    
    results = []
    
    print(f"Found {len(q1_trading_days)} trading periods. Running simulation...")
    
    # Parse interval to compute dynamic rolling window for ~3 macro months (60 trading days)
    # Assume 6.5 trading hours per day = 390 minutes
    dynamic_rolling_window = 60
    if interval.endswith("d"):
        val = interval.replace("d", "")
        dynamic_rolling_window = 60 * int(val if val else 1)
    elif interval.endswith("h"):
        val = interval.replace("h", "")
        hours = float(val if val else 1)
        bars_per_day = 6.5 / hours
        dynamic_rolling_window = int(60 * bars_per_day)
    elif interval.endswith("m"):
        val = interval.replace("m", "")
        mins = float(val if val else 1)
        bars_per_day = 390 / mins
        dynamic_rolling_window = int(60 * bars_per_day)
    elif interval.endswith("wk") or interval.endswith("w"):
        val = interval.replace("wk", "").replace("w", "")
        weeks = float(val if val else 1)
        dynamic_rolling_window = max(1, int((60 / 5) / weeks))
        
    macro_window = 60
    short_window = 21
    if interval.endswith("h"):
        hours = float(interval.replace("h", "") or 1)
        bars = 6.5 / hours
        macro_window = int(60 * bars)
        short_window = int(21 * bars)
        
    # --- TRUE EQUITY SIMULATOR STATE ---
    simulated_equity = 10000.0
    peak_equity = simulated_equity
    current_allocations = {"spx": 0.0, "short": 0.0, "btc": 0.0, "gld": 0.0, "wti": 0.0, "nvda": 0.0, "tsla": 0.0, "dell": 0.0, "spce": 0.0, "cash": 1.0}
    total_mock_trades = 0
    total_fees_paid = 0.0
    simulated_slippage_rate = 0.001 # 10 basis points slippage on turnover
    
    ledger_entries = []
    
    MIN_HOLD_BARS = 3   # For 4H: 3 bars = 12 hours minimum hold
    last_rebalance_i = -MIN_HOLD_BARS  # Initialize so first bar can trade
        
    for i, current_date in enumerate(q1_trading_days):
        # Track rolling window of feature vectors for HMM sequence inference
        if 'hmm_features_window' not in dir():
            hmm_features_window = []
            
        # 1. Slice data up to current_date
        historical_slice = raw_data[raw_data.index <= current_date]
        
        # 2. Extract series for each asset
        parsed_daily = {}
        for name, tk in ALL_YF_TICKERS.items():
            if tk in historical_slice.columns.levels[0]:
                tk_df = historical_slice[tk].dropna(how="all")
                if len(tk_df) > 10:
                    parsed_daily[name] = compute_stats(tk_df["Close"], rolling_window=dynamic_rolling_window)
                    parsed_daily[name]["raw_series"] = tk_df["Close"]
        
        spx = parsed_daily.get("SPX")
        if not spx:
            continue
            
        # 3. Compute Complex Features
        # US10Y and US2Y
        us10y_yield = 0.0
        us2y_yield = 0.0
        if "^TNX" in historical_slice.columns.levels[0]:
            tnx_slice = historical_slice["^TNX"]["Close"].dropna()
            if len(tnx_slice) > 0:
                us10y_yield = float(tnx_slice.iloc[-1])
        if "^FVX" in historical_slice.columns.levels[0]:
            fvx_slice = historical_slice["^FVX"]["Close"].dropna()
            if len(fvx_slice) > 0:
                us2y_yield = float(fvx_slice.iloc[-1])
        
        us_2s10s_spread = 0.0
        us_2s10s_spread_z = 0.0
        if "^TNX" in historical_slice.columns.levels[0] and "^FVX" in historical_slice.columns.levels[0]:
            spread_series = (historical_slice["^TNX"]["Close"] - historical_slice["^FVX"]["Close"]).dropna()
            if len(spread_series) > 0:
                us_2s10s_spread = float(spread_series.iloc[-1])
            spread_delta_series = spread_series.diff().dropna()
            if len(spread_delta_series) > 0:
                rolling = spread_delta_series.tail(dynamic_rolling_window)
                mean = rolling.mean()
                std = rolling.std()
                if std > 0:
                    us_2s10s_spread_z = (float(spread_delta_series.iloc[-1]) - mean) / std
        us10y_delta = 0.0 # Standardize to 0 for missing delta if stats aren't computed for ^TNX
        us10y_delta_z = 0.0
        if len(tnx_slice) > 1:
            us10y_delta_series = tnx_slice.diff().dropna()
            if len(us10y_delta_series) > 0:
                us10y_delta = float(us10y_delta_series.iloc[-1])
                rolling = us10y_delta_series.tail(dynamic_rolling_window)
                mean = rolling.mean()
                std = rolling.std()
                if std > 0:
                    us10y_delta_z = (us10y_delta - mean) / std
            
        # Gold Silver Ratio
        gsr_delta_pct = 0.0
        gold = parsed_daily.get("Gold")
        silver = parsed_daily.get("Silver")
        if gold and silver and silver.get("current", 0) > 0:
            gsr_current = gold["current"] / silver["current"]
            gsr_prev = gold["prev"] / silver["prev"]
            gsr_delta_pct = ((gsr_current - gsr_prev) / gsr_prev) * 100
            
        # Crypto Volatility Z-Score
        btc_tk = historical_slice["BTC-USD"]["Close"].dropna()
        btc_ret = btc_tk.pct_change() * 100
        btc_vol = btc_ret.rolling(short_window).std()
        
        # Calculate z-score using macro window
        btc_vol_macro_mean = btc_vol.rolling(macro_window).mean()
        btc_vol_macro_std = btc_vol.rolling(macro_window).std()
        
        btc_vol_z = 0.0
        if len(btc_vol) > 0 and len(btc_vol_macro_std) > 0:
            std_val = float(btc_vol_macro_std.iloc[-1])
            if std_val > 0:
                btc_vol_z = float((btc_vol.iloc[-1] - float(btc_vol_macro_mean.iloc[-1])) / std_val)
            
        # Volume Heat
        spx_close = historical_slice["^GSPC"]["Close"].dropna()
        spx_vol = historical_slice["^GSPC"]["Volume"].dropna()
        volume_heat = compute_volume_heat(spx_close, spx_vol)
        
        current_spx_val = float(spx_close.iloc[-1])
        ihi_val = volume_heat.get("institutional_heat_index", 0.0)
        
        # Run delayed self-calibration with Retail Noise Filter
        dynamic_brier_score, predictions_history = run_self_calibration(
            history=predictions_history, 
            current_spx_val=current_spx_val, 
            current_ihi=ihi_val, 
            grading_delay=5,
            interval=interval
        )
        ihi = ihi_val
        
        # 4. Construct feature vector
        def get_ret(asset):
            d = parsed_daily.get(asset, {})
            curr = d.get("current", 0)
            prev = d.get("prev", 0)
            if prev > 0: return ((curr - prev) / prev) * 100
            return 0.0

        rsi_14 = 50.0
        macd_hist = 0.0
        bbw_20 = 0.0
        vix_corr_10 = 0.0
        
        if len(spx_close) >= 30:
            delta = spx_close.diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss.replace(0, 0.0001)
            rsi = 100 - (100 / (1 + rs))
            rsi_14 = float(rsi.iloc[-1])
            
            ema12 = spx_close.ewm(span=12, adjust=False).mean()
            ema26 = spx_close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist_s = macd_line - signal_line
            macd_hist = float(macd_hist_s.iloc[-1])
            
            sma20 = spx_close.rolling(window=20).mean()
            std20_bb = spx_close.rolling(window=20).std()
            bbw = (4 * std20_bb) / sma20.replace(0, 0.0001)
            bbw_20 = float(bbw.iloc[-1])
            
            vix_close = historical_slice["^VIX"]["Close"].dropna()
            if len(vix_close) >= 20:
                spx_ret_alpha = spx_close.pct_change() * 100
                vix_ret_alpha = vix_close.pct_change() * 100
                corr_s = spx_ret_alpha.rolling(window=10).corr(vix_ret_alpha).fillna(0)
                vix_corr_10 = float(corr_s.iloc[-1])

        features_dict = {
            "spx_ret": get_ret("SPX"),
            "dxy_ret": get_ret("DXY"),
            "vix_zscore": parsed_daily.get("VIX", {}).get("z_score", 0.0),
            "Inst_Heat_Index": ihi,
            "wti_ret": get_ret("WTI"),
            "gsr_ret": gsr_delta_pct,
            "us10y_delta": us10y_delta,
            "spread_level": us_2s10s_spread,
            "btc_ret": get_ret("BTC"),
            "es_ret": get_ret("ES"),
            "nq_ret": get_ret("NQ"),
            "rty_ret": get_ret("RTY"),
            "nvda_ret": get_ret("NVDA"),
            "tsla_ret": get_ret("TSLA"),
            "dell_ret": get_ret("DELL"),
            "spce_ret": get_ret("SPCE"),
            "spx_rsi_14": rsi_14,
            "spx_macd_hist": macd_hist,
            "spx_bbw": bbw_20,
            "spx_vix_corr": vix_corr_10
        }
        
        ordered_keys = [
            "spx_ret", "dxy_ret", "vix_zscore", "Inst_Heat_Index", "wti_ret",
            "gsr_ret", "us10y_delta", "spread_level", "btc_ret",
            "es_ret", "nq_ret", "rty_ret", "nvda_ret", "tsla_ret", "dell_ret", "spce_ret",
            "spx_rsi_14", "spx_macd_hist", "spx_bbw", "spx_vix_corr"
        ]
        features_vector = [float(features_dict.get(k, 0.0)) for k in ordered_keys]
        
        hmm_features_window.append(features_vector)
        if len(hmm_features_window) > 30:   # 30 × 4H bars = 120H context
            hmm_features_window = hmm_features_window[-30:]
        
        if i < 3:
            print(f"[{current_date.strftime('%Y-%m-%d')}] Features: {features_vector}")
        
        # 5. Math Engines
        regime_probs, dom_regime, tr_risk, _ = hmm.run_inference(
            features_vector,
            features_window=hmm_features_window
        )
        if regime_probs is None:
            regime_probs = {"NEUTRAL_TRANSITIONAL": 1.0}
            
        kalman_state = risk.run_kalman_filter(
            mcs=50.0, # Dummy MCS
            sub_components={},
            hmm_regime_probs=regime_probs,
            prior_state=prior_k_state,
            prior_cov=prior_k_cov
        )
        prior_k_state = kalman_state.probabilities
        prior_k_cov = kalman_state.covariance_matrix
        
        # Run Mixture of Experts Deep Classifier (Multi-Asset)
        try:
            features_vector_clipped = np.clip(features_vector, -4.0, 4.0).tolist()
            mlp_predictions = run_multi_mlp_inference(features_vector_clipped, mlp_packages_dict, kalman_state.dominant_state)
            mlp_prob = mlp_predictions.get("spx", {}).get("bull_probability", 0.5)
            consensus = mlp_predictions.get("spx", {}).get("consensus_score", 0.0)
        except Exception as e:
            print(f"MLP Error: {e}")
            mlp_predictions = {"spx": {"bull_probability": 0.5, "consensus_score": 0.0}}
            mlp_prob = 0.5
            consensus = 0.0
            
        # Capitulation Override Detection
        spx_ret_z = parsed_daily.get("SPX", {}).get("z_score", 0.0)
        ihi_val = ihi
        is_capitulation_override = False
        if spx_ret_z < -1.5 and spx_ret_z >= -3.0 and ihi_val > 0.0 and mlp_prob > 0.5:
            is_capitulation_override = True

        # Momentum Ignition Override Detection
        is_momentum_override = False
        if spx_ret_z > 1.0 and ihi_val > 0.1 and 0.4 < mlp_prob <= 0.80:
            is_momentum_override = True

        # Black Swan Circuit Breaker
        is_black_swan = False
        if spx_ret_z < -3.5:
            is_black_swan = True
            
        # Bull Trap Inversion
        is_bull_trap = False
        if spx_ret_z > 2.0 and parsed_daily.get("VIX", {}).get("current", 0) > 25:
            is_bull_trap = True

        # Macro Trend Filter Check
        current_spx_close = spx_data.loc[current_date]["Close"]
        current_spx_ema = spx_ema.loc[current_date]
        is_downtrend = current_spx_close < current_spx_ema

        peak_equity = max(peak_equity, simulated_equity)
        equity_drawdown = (peak_equity - simulated_equity) / peak_equity if peak_equity > 0 else 0.0

        kelly_dict = risk.compute_multi_asset_kelly(
            mlp_predictions=mlp_predictions,
            dominant_state=kalman_state.dominant_state,
            brier_score=dynamic_brier_score,
            duration_days=5,
            is_capitulation_override=is_capitulation_override,
            is_momentum_override=is_momentum_override,
            is_black_swan=is_black_swan,
            is_bull_trap=is_bull_trap,
            hmm_regime=dom_regime,
            current_ihi=ihi_val,
            is_downtrend=is_downtrend,
            max_kelly_cap=0.30 if interval == "4h" else 0.40,
            equity_drawdown=equity_drawdown
        )
        spx_kelly = kelly_dict.get("SPX_Kelly", 0.0)
        
        # Track for self-calibration 5-bar delayed grading
        predictions_history.append({
            "predicted_risk_on": mlp_prob,
            "spx_val_at_prediction": current_spx_val,
            "target_graded": False
        })
        
        # Multi-Asset 1-Bar Forward Return tracking (Continuous Compounding Simulator)
        future_slice_spx = raw_data["^GSPC"][raw_data["^GSPC"].index > current_date]
        future_slice_btc = raw_data["BTC-USD"][raw_data["BTC-USD"].index > current_date]
        future_slice_gld = raw_data["GC=F"][raw_data["GC=F"].index > current_date]
        future_slice_wti = raw_data["CL=F"][raw_data["CL=F"].index > current_date]
        future_slice_nvda = raw_data["NVDA"][raw_data["NVDA"].index > current_date]
        future_slice_tsla = raw_data["TSLA"][raw_data["TSLA"].index > current_date]
        future_slice_dell = raw_data["DELL"][raw_data["DELL"].index > current_date]
        future_slice_spce = raw_data["SPCE"][raw_data["SPCE"].index > current_date]

        def get_1bar_ret(fs, current_val):
            if len(fs) >= 1:
                future = fs["Close"].iloc[0]
                if current_val > 0 and not pd.isna(current_val) and not pd.isna(future):
                    return float((future - current_val) / current_val)
            return 0.0

        spx_1bar = get_1bar_ret(future_slice_spx, current_spx_val)
        btc_1bar = get_1bar_ret(future_slice_btc, float(parsed_daily.get("BTC", {}).get("current", 0)))
        gld_1bar = get_1bar_ret(future_slice_gld, float(parsed_daily.get("Gold", {}).get("current", 0)))
        wti_1bar = get_1bar_ret(future_slice_wti, float(parsed_daily.get("WTI", {}).get("current", 0)))
        nvda_1bar = get_1bar_ret(future_slice_nvda, float(parsed_daily.get("NVDA", {}).get("current", 0)))
        tsla_1bar = get_1bar_ret(future_slice_tsla, float(parsed_daily.get("TSLA", {}).get("current", 0)))
        dell_1bar = get_1bar_ret(future_slice_dell, float(parsed_daily.get("DELL", {}).get("current", 0)))
        spce_1bar = get_1bar_ret(future_slice_spce, float(parsed_daily.get("SPCE", {}).get("current", 0)))
        
        # Calculate Forward 5d return strictly for edge-accuracy scoring (legacy reporting)
        def get_fwd_5d(fs):
            if len(fs) >= 5:
                curr = fs["Close"].iloc[0]
                future = fs["Close"].iloc[4]
                if curr > 0 and not pd.isna(curr) and not pd.isna(future):
                    return float(((future - curr) / curr) * 100)
            return 0.0
            
        spx_fwd_5d = get_fwd_5d(future_slice_spx)
        
        short_kelly = kelly_dict.get("Short_Kelly", 0.0)
        btc_kelly = kelly_dict.get("BTC_Kelly", 0.0)
        gld_kelly = kelly_dict.get("GLD_Kelly", 0.0)
        wti_kelly = kelly_dict.get("WTI_Kelly", 0.0)
        nvda_kelly = kelly_dict.get("NVDA_Kelly", 0.0)
        tsla_kelly = kelly_dict.get("TSLA_Kelly", 0.0)
        dell_kelly = kelly_dict.get("DELL_Kelly", 0.0)
        spce_kelly = kelly_dict.get("SPCE_Kelly", 0.0)
        cash_kelly = kelly_dict.get("Cash", 0.0)
        
        # 1. Apply Mark-to-Market Growth based on current (previous bar's) allocations
        portfolio_1bar_return = (
            (current_allocations["spx"] * spx_1bar) +
            (current_allocations["short"] * -spx_1bar) +
            (current_allocations["btc"] * btc_1bar) +
            (current_allocations["gld"] * gld_1bar) +
            (current_allocations["wti"] * wti_1bar) +
            (current_allocations["nvda"] * nvda_1bar) +
            (current_allocations["tsla"] * tsla_1bar) +
            (current_allocations["dell"] * dell_1bar) +
            (current_allocations["spce"] * spce_1bar)
        )
        simulated_equity *= (1.0 + portfolio_1bar_return)
        
        # 2. Rebalance to Target Kellys — only if min hold period has elapsed
        target_allocations = {"spx": spx_kelly, "short": short_kelly, "btc": btc_kelly, "gld": gld_kelly, "wti": wti_kelly, "nvda": nvda_kelly, "tsla": tsla_kelly, "dell": dell_kelly, "spce": spce_kelly, "cash": cash_kelly}
        
        if use_rl_agent and rl_agent_instance:
            rl_allocs = rl_agent_instance.predict_allocations(features_vector_clipped, current_allocations)
            if rl_allocs:
                target_allocations = {
                    "spx": rl_allocs.get("SPX_Kelly", 0.0),
                    "short": rl_allocs.get("Short_Kelly", 0.0),
                    "btc": rl_allocs.get("BTC_Kelly", 0.0),
                    "gld": rl_allocs.get("GLD_Kelly", 0.0),
                    "wti": rl_allocs.get("WTI_Kelly", 0.0),
                    "nvda": rl_allocs.get("NVDA_Kelly", 0.0),
                    "tsla": rl_allocs.get("TSLA_Kelly", 0.0),
                    "dell": rl_allocs.get("DELL_Kelly", 0.0),
                    "spce": rl_allocs.get("SPCE_Kelly", 0.0),
                    "cash": rl_allocs.get("Cash", 0.0)
                }
            
        bars_since_rebalance = i - last_rebalance_i
        
        if bars_since_rebalance >= MIN_HOLD_BARS:
            turnover_fraction = sum(abs(target_allocations[k] - current_allocations[k]) for k in ["spx", "short", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"])
            if turnover_fraction > 0.10:  # Only trade if drift > 10% of portfolio
                slippage_cost = turnover_fraction * simulated_equity * simulated_slippage_rate
                simulated_equity -= slippage_cost
                total_fees_paid += slippage_cost
                total_mock_trades += 1
                last_rebalance_i = i
                
                ticker_map = {"spx": "SPX", "short": "SPX", "btc": "BTC", "gld": "Gold", "wti": "WTI", "nvda": "NVDA", "tsla": "TSLA", "dell": "DELL", "spce": "SPCE"}
                
                # Log mock trade to ledger
                for k, target_alloc in target_allocations.items():
                    if k == "cash": continue
                    current_alloc = current_allocations[k]
                    if abs(target_alloc - current_alloc) > 0.05:
                        action = "BUY" if target_alloc > current_alloc else "SELL"
                        asset_name = k.upper()
                        
                        mapped_key = ticker_map.get(k, "SPX")
                        actual_price = float(parsed_daily.get(mapped_key, {}).get("current", 100.0))
                        if actual_price <= 0: actual_price = 100.0
                        
                        if asset_name == "SHORT":
                            asset_name = "SH"  # ProShares Short S&P500 ETF
                            
                        trade_value = abs(target_alloc - current_alloc) * simulated_equity
                        trade_shares = trade_value / actual_price
                        
                        # Statistics
                        prob = mlp_predictions.get(k, {}).get("bull_probability", 0.0)
                        if k == "short": prob = 1.0 - mlp_predictions.get("spx", {}).get("bull_probability", 0.5)
                        
                        stat_str = f"Prob:{prob:.2f} | Reg:{dom_regime}"
                        
                        ledger_entries.append(f"{current_date.strftime('%Y-%m-%d %H:%M:%S')},{action},{asset_name},{trade_shares:.4f},{actual_price:.2f},{trade_value:.2f},{stat_str}")

            # 3. Update Allocations
                current_allocations = target_allocations
        # else: hold current allocations unchanged — no trade, no fee
        
        # Backwards compatible fwd_5d_ret calculation for the report logging
        fwd_5d_ret = (
            (spx_kelly * spx_fwd_5d) +
            (short_kelly * -spx_fwd_5d) +
            (btc_kelly * get_fwd_5d(future_slice_btc)) +
            (gld_kelly * get_fwd_5d(future_slice_gld)) +
            (wti_kelly * get_fwd_5d(future_slice_wti)) +
            (nvda_kelly * get_fwd_5d(future_slice_nvda)) +
            (tsla_kelly * get_fwd_5d(future_slice_tsla)) +
            (dell_kelly * get_fwd_5d(future_slice_dell)) +
            (spce_kelly * get_fwd_5d(future_slice_spce))
        )
        # Final forward return validation
        results.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "spx_close": current_spx_val,
            "dom_regime": dom_regime,
            "kalman_state": kalman_state.dominant_state,
            "mlp_prob": mlp_prob,
            "consensus": consensus,
            "spx_fwd_5d": spx_fwd_5d,
            "kelly_exposure": spx_kelly,
            "short_exposure": short_kelly,
            "btc_exposure": btc_kelly,
            "gld_exposure": gld_kelly,
            "wti_exposure": wti_kelly,
            "safe_haven_exposure": kelly_dict.get("Cash", 0.0), # Representing Cash now
            "fwd_5d_ret": fwd_5d_ret
        })

    # 7. Generate Output Report
    win_count = 0
    total_drawdowns = 0
    drawdown_protected = 0
    
    for r in results:
        # Evaluate Multi-Asset Win logic
        # Positive generated alpha on the portfolio is a win
        spx_ret_fwd = r.get("spx_fwd_5d", 0.0)
        
        if r["fwd_5d_ret"] > 0.01:
            win_count += 1
        elif abs(r["fwd_5d_ret"]) <= 0.01 and spx_ret_fwd < 0:
            # Model went to cash and dodged an SPX drop (Capital Preservation Win)
            win_count += 1
            
        # Drawdown protection metric (if SPX goes down > 1.5%, were we hedged/short?)
        if r["fwd_5d_ret"] < -1.5 and (r["kelly_exposure"] < 0.2 or r["short_exposure"] > 0.1 or r["safe_haven_exposure"] > 0.5):
            drawdown_protected += 1
        if r["fwd_5d_ret"] < -1.5:
            total_drawdowns += 1
                
    # Calculate accuracy based only on active trades (where exposure was taken or capital preservation triggered)
    active_periods = sum(1 for r in results if abs(r["fwd_5d_ret"]) > 0.01 or (abs(r["fwd_5d_ret"]) <= 0.01 and r.get("spx_fwd_5d", 0.0) < 0))
    if active_periods == 0:
        accuracy = 0.0
    else:
        accuracy = (win_count / active_periods) * 100
        
    protection_rate = (drawdown_protected / total_drawdowns * 100) if total_drawdowns > 0 else 100.0
    
    # Generate Probability Calibration Table
    prob_bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    prob_labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
    
    calibration_data = {label: {"count": 0, "wins": 0, "total_ret": 0.0} for label in prob_labels}
    
    for r in results:
        p = r["mlp_prob"]
        ret = float(r["fwd_5d_ret"]) if not pd.isna(r["fwd_5d_ret"]) else 0.0
        for i in range(len(prob_bins) - 1):
            if prob_bins[i] <= p <= prob_bins[i+1]:
                label = prob_labels[i]
                calibration_data[label]["count"] += 1
                calibration_data[label]["total_ret"] += ret
                if ret > 0:
                    calibration_data[label]["wins"] += 1
                break
                
    prob_table = "## Deep Learning Probability Calibration\n"
    prob_table += "| Probability Bucket | Occurrences | Win Rate | Avg Forward Return |\n"
    prob_table += "|--------------------|-------------|----------|--------------------|\n"
    for label in prob_labels:
        c = calibration_data[label]["count"]
        if c > 0:
            wr = (calibration_data[label]["wins"] / c) * 100
            avg_ret = calibration_data[label]["total_ret"] / c
            prob_table += f"| {label} | {c} | {wr:.1f}% | {avg_ret:.3f}% |\n"
        else:
            prob_table += f"| {label} | 0 | 0.0% | 0.000% |\n"

    # Build Simulated Trading Ledger Analysis
    pnl_pct = ((simulated_equity - 10000.0) / 10000.0) * 100
    paper_section = "## Simulated Trading Ledger Analysis (Continuous Compounding)\n"
    paper_section += f"- **Mock Execution PnL:** {pnl_pct:.2f}% (Total Equity: ${simulated_equity:,.2f})\n"
    paper_section += f"- **Total Executed Rotations:** {total_mock_trades}\n"
    paper_section += f"- **Total Slippage/Fees Paid:** ${total_fees_paid:,.2f}\n"
            
    report = f"""# Quantitative Engine Backtest: Detailed (Rolling 6-Month)

**Test Period:** {q1_start.strftime("%Y-%m-%d")} to {q1_end.strftime("%Y-%m-%d")}
**Samples:** {len(results)} Trading Periods

## Performance Summary
- **Portfolio Win Rate (Edge Accuracy):** {accuracy:.1f}%
- **Crash Protection Rate:** {protection_rate:.1f}% ({drawdown_protected}/{total_drawdowns} major dips avoided)
- **Average Kelly Allocation:** {np.mean([r['kelly_exposure'] for r in results]):.3f}

{prob_table}

{paper_section}

## Detailed Daily Log
| Date | SPX Close | HMM Regime | Kalman State | Ensemble Prob | Consensus | SPX Kelly | Short Kelly | BTC Kelly | GLD Kelly | WTI Kelly | Cash | Portfolio 5D PnL |
|------|-----------|------------|--------------|---------------|-----------|-----------|-------------|-----------|-----------|-----------|------|------------------|
"""
    for r in results:
        report += f"| {r['date']} | {r['spx_close']} | {r['dom_regime']} | {r['kalman_state']} | {r['mlp_prob']:.3f} | {r['consensus']:.1f} | {r['kelly_exposure']} | {r['short_exposure']} | {r['btc_exposure']} | {r['gld_exposure']} | {r['wti_exposure']} | {r['safe_haven_exposure']} | {r['fwd_5d_ret']:.3f}% |\n"
        
    report_path = os.path.join(os.path.dirname(__file__), "..", "reports", f"backtest_extended_results_{interval}.md")
    with open(report_path, "w") as f:
        f.write(report)
        
    # Overwrite the paper trading portfolio so the UI reflects the backtest's final simulated state
    final_cash = simulated_equity * current_allocations.get("cash", 1.0)
    final_positions = {}
    for k, alloc in current_allocations.items():
        if k != "cash" and alloc > 0:
            asset_label = k.upper()
            if asset_label == "SHORT":
                asset_label = "SH"
            # Approximation of shares: alloc * simulated_equity / 100
            final_positions[asset_label] = (alloc * simulated_equity) / 100.0
            
    portfolio_state = {
        "cash": final_cash,
        "positions": final_positions,
        "position_details": {},
        "total_equity": simulated_equity,
        "peak_equity": simulated_equity,
        "last_update": datetime.now().isoformat(),
        "total_fees_paid": total_fees_paid,
        "win_rate": accuracy
    }
    
    portfolio_path = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trading", "backtest_portfolio.json")
    os.makedirs(os.path.dirname(portfolio_path), exist_ok=True)
    with open(portfolio_path, "w") as f:
        json.dump(portfolio_state, f, indent=4)
        
    ledger_path = os.path.join(os.path.dirname(__file__), "..", "data", "paper_trading", "backtest_ledger.csv")
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    with open(ledger_path, "w") as f:
        f.write("timestamp,action,ticker,shares,price,value,stats\n")
        f.write("\n".join(ledger_entries) + "\n")
        
    print("Backtest complete! Report generated and Paper Trading UI state updated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval",   type=str, default="1d", choices=["1d", "1wk", "1h", "4h"])
    parser.add_argument("--use_rl", action="store_true", help="Enable RL Agent for allocations")
    parser.add_argument("--start-date", type=str, default=None,
                        help="Backtest start date (YYYY-MM-DD). Defaults to Jan 1 of current year.")
    parser.add_argument("--end-date",   type=str, default=None,
                        help="Backtest end date (YYYY-MM-DD). Defaults to today minus 5 days.")
    args = parser.parse_args()
    run_backtest(
        interval=args.interval,
        use_rl_agent=args.use_rl,
        start_date=args.start_date,
        end_date=args.end_date
    )
