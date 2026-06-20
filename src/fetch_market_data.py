import os
import json
import argparse
import traceback
import feedparser
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import src.config_loader
import joblib
from collections import deque

from src.observability.logger import get_logger
from src.observability.event_bus import EventBus
from src.data_lake.lake_manager import LakeManager
from src.adapters.yahoo_adapter import YahooAdapter
from src.adapters.gemini_adapter import GeminiAdapter
from src.adapters.forexfactory_adapter import ForexFactoryAdapter
from src.adapters.paper_broker import PaperBroker
from src.engines.trend_engine import TrendEngine
from src.engines.smc_engine import SMCEngine
from src.engines.session_engine import SessionEngine
from src.engines.liquidity_engine import LiquidityEngine
from src.engines.regime_ensemble import RegimeEnsemble
from src.engines.risk_engine import RiskEngine
from src.engines.consensus_engine import ConsensusEngine
from src.engines.entry_engine import EntryEngine
from src.engines.frequency_controller import FrequencyController
from src.schemas.models import MarketSnapshot, RegimeState, MarketExtremes, NewsSignal, KalmanState, EconomicCalendar
from src.engines.feature_engine import (
    ALL_YF_TICKERS, get_fred_key, get_signature_salt, sign_snapshot_payload,
    check_mathematical_consistency, append_to_immutable_chain,
    compute_stats, compute_volume_heat, compute_market_extremes,
    compute_garch_volatility, load_mlp_models, run_multi_mlp_inference,
    compute_weekly_liquidity_boundaries, calculate_model_tvd,
    calculate_bayesian_conditional_probability, run_self_calibration,
    compute_mcs, garch_targets
)

logger = get_logger("conductor")

def fetch_rss_headlines():
    urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    ]
    headlines = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                headlines.append(entry.title)
        except Exception as e:
            logger.error(f"RSS fetch failed: {e}")
    return headlines

class Conductor:
    def __init__(self, interval="1d", use_1h_context=False):
        self.interval = interval
        self.use_1h_context = use_1h_context
        logger.info(f"Initializing v6.0.0 Real-Time Event-Driven Conductor (Interval: {interval}, 1H-Context: {use_1h_context})")
        
        self.lake_manager = LakeManager()
        self.event_bus = EventBus()
        self.event_bus.set_interceptor(self.lake_manager.log_event)
        self.paper_broker = PaperBroker(os.path.join(os.path.dirname(__file__), "..", "data"))
        
        fred_key = get_fred_key()
        self.data_broker = YahooAdapter(fred_key=fred_key)
        self.ff_adapter = ForexFactoryAdapter()
        self.gemini_adapter = GeminiAdapter()
        
        self.trend_engine = TrendEngine()
        self.smc_engine = SMCEngine()
        self.session_engine = SessionEngine()
        self.liquidity_engine = LiquidityEngine()
        self.regime_ensemble = RegimeEnsemble()
        self.risk_engine = RiskEngine()
        self.consensus_engine = ConsensusEngine()
        self.entry_engine = EntryEngine()
        self.entry_quality_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "entry_quality.json")
        self.frequency_controller = FrequencyController()
        self.frequency_state_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "frequency_state.json")
        
        # RL Agent sizing option
        self.use_rl_agent = False
        from src.engines.rl_agent import RLAgent
        self.rl_agent = RLAgent(interval=self.interval) if self.use_rl_agent else None
        
        self.snapshot = MarketSnapshot()
        
        self.clean_daily = {}
        self.bonds = {}
        self.features_vector = []
        self.features_window = deque(maxlen=30)
        self.FEATURES_WINDOW_SIZE = 30
        self.last_rebalance_bar = -1
        self.bar_count = 0
        self.MIN_HOLD_BARS = 1
        self.dynamic_rolling_window = 20   # 20-bar rolling window for VIX z-score
        self._spx_raw_series = None
        self.feature_metadata = {}
        self.ordered_feature_keys = [
            ("spx_ret", "SPX", "delta_pct"),
            ("dxy_ret", "DXY", "delta_pct"),
            ("vix_zscore", "VIX", "z_score"),
            ("Inst_Heat_Index", "volume_activity_heat", "institutional_heat_index"),
            ("wti_ret", "WTI", "delta_pct"),
            ("gsr_ret", "gold_to_silver_ratio", "delta_pct"),
            ("us10y_delta", "bonds", "delta"),
            ("spread_level", "bonds", "spread_2s10s"),
            ("btc_ret", "BTC", "delta_pct"),
            ("nvda_ret", "NVDA", "delta_pct"),
            ("tsla_ret", "TSLA", "delta_pct"),
            ("dell_ret", "DELL", "delta_pct"),
            ("spce_ret", "SPCE", "delta_pct"),
            ("spx_rsi_14", "SPX_Alpha", "rsi_14"),
            ("spx_macd_hist", "SPX_Alpha", "macd_hist"),
            ("spx_bbw", "SPX_Alpha", "bbw_20"),
            ("vix_corr", "SPX_Alpha", "vix_corr_10"),
        ]
        
        # Register Event Callbacks
        self.event_bus.subscribe("SystemStart", self.handle_system_start)
        self.event_bus.subscribe("DataFetched", self.handle_data_fetched)
        self.event_bus.subscribe("FeaturesEngineered", self.handle_features_engineered)
        self.event_bus.subscribe("EnginesCompleted", self.handle_engines_completed)
        self.event_bus.subscribe("PipelineComplete", self.handle_pipeline_complete)

    def run(self):
        self.event_bus.publish("SystemStart", {"timestamp": datetime.now(timezone.utc).isoformat()})

    def handle_system_start(self, payload):
        logger.info(f"Starting Data Ingestion Phase via Event Bus for {self.interval}")
        tickers = list(ALL_YF_TICKERS.values())
        raw_daily_data = self.data_broker.fetch_ohlcv_daily(tickers, period="180d", interval=self.interval)
        raw_hourly_data = self.data_broker.fetch_ohlcv_hourly(tickers, period="5d")
        
        calendar_data = self.ff_adapter.fetch_calendar()
        
        self.lake_manager.save_tabular(raw_daily_data, "raw_daily_ohlcv.parquet")
        self.lake_manager.save_tabular(raw_hourly_data, "raw_hourly_ohlcv.parquet")
        
        self.event_bus.publish("DataFetched", {
            "daily": raw_daily_data, 
            "hourly": raw_hourly_data,
            "calendar": calendar_data.model_dump()
        })

    def handle_data_fetched(self, payload):
        raw_daily_data = payload["daily"]
        raw_hourly_data = payload["hourly"]
        self.raw_hourly_data = raw_hourly_data
        self.raw_daily_data = raw_daily_data
        
        self.snapshot.economic_calendar = EconomicCalendar.model_validate(payload.get("calendar", {}))
        
        def parse_assets(raw_df):
            parsed = {}
            if not isinstance(raw_df.columns, pd.MultiIndex):
                return parsed
            for name, tk in ALL_YF_TICKERS.items():
                if tk in raw_df.columns.levels[0]:
                    tk_df = raw_df[tk].dropna(how="all")
                    if len(tk_df) > 1:
                        parsed[name] = compute_stats(tk_df["Close"])
                        parsed[name]["raw_series"] = tk_df["Close"]
            return parsed
            
        parsed_daily = parse_assets(raw_daily_data)
        parsed_hourly = parse_assets(raw_hourly_data)
        
        self._spx_raw_series = parsed_daily.get("SPX", {}).get("raw_series")
        
        clean_daily = {}
        for k, v in parsed_daily.items():
            clean_daily[k] = {ik: iv for ik, iv in v.items() if ik != "raw_series"}
            
        # Calculate US10Y and spread z-scores
        us10y_hist = self.data_broker.fetch_yield_history("DGS10")
        us2y_hist = self.data_broker.fetch_yield_history("DGS2")
        
        us10y_delta = 0.0
        us10y_delta_z = 0.0
        if not us10y_hist.empty and len(us10y_hist) >= 60:
            deltas = us10y_hist.diff().dropna()
            m, s = deltas.mean(), deltas.std()
            if len(deltas) > 0: us10y_delta = float(deltas.iloc[-1])
            if s > 0: us10y_delta_z = float((deltas.iloc[-1] - m) / s)
            
        spread_z = 0.0
        if not us10y_hist.empty and not us2y_hist.empty and len(us10y_hist) >= 60 and len(us2y_hist) >= 60:
            spreads = (us10y_hist - us2y_hist).dropna().diff().dropna()
            m, s = spreads.mean(), spreads.std()
            if s > 0: spread_z = float((spreads.iloc[-1] - m) / s)
            
        bonds = {
            "US2Y": {"current": self.data_broker.fetch_yield("DGS2")},
            "US10Y": {"current": self.data_broker.fetch_yield("DGS10"), "delta": round(us10y_delta, 4), "delta_zscore": round(us10y_delta_z, 4)},
            "spread_zscore": round(spread_z, 4)
        }
        if bonds["US2Y"]["current"] and bonds["US10Y"]["current"]:
            bonds["spread_2s10s"] = round(bonds["US10Y"]["current"] - bonds["US2Y"]["current"], 4)
        else: bonds["spread_2s10s"] = 0.0
        
        if abs(bonds.get("spread_2s10s", 0.0)) > 5.0:
            logger.warning(f"Yield spread anomaly detected: {bonds['spread_2s10s']}. Possible unit mismatch.")
            bonds["spread_2s10s"] = 0.0
        
        self.clean_daily = clean_daily
        self.bonds = bonds
        self.snapshot.bonds = bonds
        
        # GARCH & Extremes
        garch_layer = {}
        for name, ticker in garch_targets.items():
            cond_vol, regime, f_vol = compute_garch_volatility(ticker)
            garch_layer[name] = {"conditional_vol": cond_vol if cond_vol else 0.0, "regime": regime}
            
        self.garch_layer = garch_layer
            
        spx_s = parsed_daily.get("SPX", {}).get("raw_series")
        vix_s = parsed_daily.get("VIX", {}).get("raw_series")
        if spx_s is not None and len(spx_s) >= 30:
            clean_daily["SPX"]["ema_20"] = float(spx_s.ewm(span=20, adjust=False).mean().iloc[-1])
            
            # SPX RSI 14
            delta = spx_s.diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss.replace(0, 0.0001)
            rsi = 100 - (100 / (1 + rs))
            
            # SPX MACD Hist
            ema12 = spx_s.ewm(span=12, adjust=False).mean()
            ema26 = spx_s.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            
            # SPX BBW 20
            sma20 = spx_s.rolling(window=20).mean()
            std20_bb = spx_s.rolling(window=20).std()
            bbw = (4 * std20_bb) / sma20.replace(0, 0.0001)
            
            # SPX VIX Corr 10
            vix_corr = 0.0
            if vix_s is not None and len(vix_s) >= 20:
                spx_ret_alpha = spx_s.pct_change() * 100
                vix_ret_alpha = vix_s.pct_change() * 100
                corr_s = spx_ret_alpha.rolling(window=10).corr(vix_ret_alpha).fillna(0)
                vix_corr = float(corr_s.iloc[-1])
            
            clean_daily["SPX_Alpha"] = {
                "rsi_14": float(rsi.iloc[-1]),
                "macd_hist": float(macd_hist.iloc[-1]),
                "bbw_20": float(bbw.iloc[-1]),
                "vix_corr_10": float(vix_corr)
            }
        else:
            clean_daily["SPX_Alpha"] = {
                "rsi_14": 50.0,
                "macd_hist": 0.0,
                "bbw_20": 0.0,
                "vix_corr_10": 0.0
            }
            
        vix_s = parsed_daily.get("VIX", {}).get("raw_series")
        if vix_s is not None and len(vix_s) >= 20:
            v_mean = vix_s.rolling(self.dynamic_rolling_window).mean().iloc[-1]
            v_std = vix_s.rolling(self.dynamic_rolling_window).std().iloc[-1]
            v_zscore = (vix_s.iloc[-1] - v_mean) / v_std if v_std > 0 else 0.0
            if "VIX" not in self.clean_daily:
                self.clean_daily["VIX"] = {}
            self.clean_daily["VIX"]["z_score"] = float(v_zscore)
            
        vvix_s = parsed_daily.get("VVIX", {}).get("raw_series")
        dxy_s = parsed_daily.get("DXY", {}).get("raw_series")
        vix9d_s = parsed_daily.get("VIX9D", {}).get("raw_series")
        
        extremes_dict = compute_market_extremes(spx_s, vix_s, vvix_s, dxy_s, vix9d_s)
        self.snapshot.market_extremes_insight = MarketExtremes(**extremes_dict)
        
        spx_series = raw_daily_data["^GSPC"]["Close"].dropna() if "^GSPC" in raw_daily_data.columns.levels[0] else pd.Series()
        spx_vol = raw_daily_data["^GSPC"]["Volume"].dropna() if "^GSPC" in raw_daily_data.columns.levels[0] else pd.Series()
        self.clean_daily["volume_activity_heat"] = compute_volume_heat(spx_series, spx_vol)
        
        gold = clean_daily.get("Gold")
        silver = clean_daily.get("Silver")
        if gold and silver and silver.get("current", 0) > 0:
            gsr_current = gold["current"] / silver["current"]
            gsr_prev = gold["prev"] / silver["prev"]
            gsr_delta_pct = ((gsr_current - gsr_prev) / gsr_prev) * 100
            self.clean_daily["gold_to_silver_ratio"] = {"current": round(gsr_current, 3), "prev": round(gsr_prev, 3), "delta_pct": round(gsr_delta_pct, 3)}
            
        ibit = clean_daily.get("IBIT")
        etha = clean_daily.get("ETHA")
        if ibit and etha and ibit.get("z_score") is not None and etha.get("z_score") is not None:
            mfi_z = (ibit["z_score"] + etha["z_score"]) / 2
            self.clean_daily["institutional_crypto_mfi"] = {
                "composite_z": round(mfi_z, 3),
                "flow_regime": "INFLOW" if mfi_z > 1.0 else "OUTFLOW" if mfi_z < -1.0 else "FLAT"
            }
            
        hyg = clean_daily.get("HYG")
        lqd = clean_daily.get("LQD")
        if hyg and lqd and hyg.get("z_score") is not None and lqd.get("z_score") is not None:
            credit_z = (hyg["z_score"] + lqd["z_score"]) / 2
            self.clean_daily["credit_stress_proxy"] = {
                "composite_z": round(credit_z, 3), 
                "label": "CRITICAL" if credit_z < -2.0 else "ELEVATED" if credit_z < -1.0 else "NORMAL"
            }
            
        self.features_vector = []
        self.feature_metadata = {}
        for label, category, key in self.ordered_feature_keys:
            val = 0.0
            try:
                if category == "bonds":
                    if key == "delta_zscore" and bonds.get("US10Y"): val = bonds["US10Y"].get("delta_zscore", 0.0)
                    elif key == "delta" and bonds.get("US10Y"): val = bonds["US10Y"].get("delta", 0.0)
                    elif key == "spread_zscore": val = bonds.get("spread_zscore", 0.0)
                    elif key == "spread_2s10s": val = bonds.get("spread_2s10s", 0.0)
                else: val = self.clean_daily.get(category, {}).get(key, 0.0)
                if val is None: val = 0.0
            except Exception: pass
            self.features_vector.append(float(val))
            self.feature_metadata[label] = float(val)
            
        self.event_bus.publish("FeaturesEngineered", {"vector": self.features_vector, "meta": self.feature_metadata})

    def handle_features_engineered(self, payload):
        # Manage persistent rolling window of features for HMM inference
        window_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", f"features_window_{self.interval}.json")
        persistent_window = []
        if os.path.exists(window_path):
            try:
                with open(window_path, 'r') as f:
                    persistent_window = json.load(f)
            except Exception:
                pass
                
        persistent_window.append(self.features_vector)
        # Keep last 6 bars for the HMM sequence
        if len(persistent_window) > 6:
            persistent_window = persistent_window[-6:]
            
        try:
            with open(window_path, 'w') as f:
                json.dump(persistent_window, f)
        except Exception as e:
            logger.warning(f"Could not save features window: {e}")
            
        self.features_window = persistent_window
        
        if self.use_1h_context:
            logger.info("Using 1H context for Daily Execution.")
            prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "market_snapshot_prior.json")
            if os.path.exists(prior_path):
                try:
                    with open(prior_path, 'r') as f:
                        prior = json.load(f)
                    hmm_beta_probs = prior.get("regime", {}).get("probabilities", {})
                    hmm_beta_dom = prior.get("regime", {}).get("dominant_regime", "NEUTRAL_TRANSITIONAL")
                    hmm_alpha_probs = prior.get("regime", {}).get("tactical_alpha_probabilities", {})
                    hmm_alpha_dom = prior.get("regime", {}).get("tactical_alpha_regime", "NEUTRAL_TRANSITIONAL")
                    tr_risk = prior.get("regime", {}).get("transition_risk", 0.0)
                except Exception as e:
                    logger.warning(f"Error reading 1H context: {e}. Falling back.")
                    hmm_beta_probs, hmm_beta_dom, hmm_alpha_probs, hmm_alpha_dom, tr_risk = {}, "NEUTRAL_TRANSITIONAL", {}, "NEUTRAL_TRANSITIONAL", 0.0
            else:
                logger.warning("No prior 1H snapshot found! Falling back to flat probabilities.")
                hmm_beta_probs, hmm_beta_dom, hmm_alpha_probs, hmm_alpha_dom, tr_risk = {}, "NEUTRAL_TRANSITIONAL", {}, "NEUTRAL_TRANSITIONAL", 0.0
        else:
            try:
                spx_daily = self.raw_daily_data["^GSPC"].dropna()
            except Exception:
                spx_daily = pd.DataFrame()
            try:
                spx_hourly = self.raw_hourly_data["^GSPC"].dropna()
            except Exception:
                spx_hourly = pd.DataFrame()

            trend_state = self.trend_engine.score(spx_daily) if not spx_daily.empty else {}
            smc_state = self.smc_engine.compute(spx_daily) if not spx_daily.empty else None
            smc_dict = smc_state.__dict__ if smc_state else {}
            
            # ORB requires hourly bars
            orb_res = self.session_engine.compute_orb_signal(spx_hourly) if not spx_hourly.empty else {}
            # TD9 requires 1D closes for macro exhaustion
            td9_res = self.session_engine.td9_exhaustion_signal(spx_daily["Close"]) if not spx_daily.empty else {}
            # Session bias
            from datetime import datetime, timezone
            sess_bias = self.session_engine.compute_session_state(spx_hourly, datetime.now(timezone.utc)) if not spx_hourly.empty else {}
            
            session_state = {**orb_res, **td9_res, **sess_bias}
            
            liq_state = self.liquidity_engine.compute(spx_daily) if not spx_daily.empty else {}

            hmm_beta_probs, hmm_beta_dom, tr_risk, _ = self.regime_ensemble.compute(
                trend_state, smc_dict, session_state, liq_state, self.feature_metadata
            )
            hmm_alpha_probs = hmm_beta_probs
            hmm_alpha_dom = hmm_beta_dom
            
            # Populate snapshot models
            from src.schemas.models import TrendState, SMCState, SessionState, LiquidityState
            if trend_state: self.snapshot.trend_state = TrendState(**trend_state)
            if smc_state: self.snapshot.smc_state = SMCState(**smc_dict)
            if session_state: self.snapshot.session_state = SessionState(**session_state)
            if liq_state: self.snapshot.liquidity_state = LiquidityState(**liq_state)
        
        current_regime = hmm_beta_dom if hmm_beta_dom else "NEUTRAL_TRANSITIONAL"
        
        # Backend Settings Sync & Isolation: Fetch active tickers to simulate independent execution
        trading_settings_path = os.path.join(os.path.dirname(__file__), "..", "config", "trading_settings.json")
        active_tickers = ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]
        if os.path.exists(trading_settings_path):
            try:
                with open(trading_settings_path, 'r') as f:
                    settings_data = json.load(f)
                    if "active_tickers" in settings_data:
                        active_tickers = settings_data["active_tickers"]
            except: pass
            
        mlp_packages = load_mlp_models(self.interval, assets=active_tickers)
        features_vector_clipped = np.clip(self.features_vector, -4.0, 4.0).tolist()
        mlp_state = run_multi_mlp_inference(features_vector_clipped, mlp_packages, current_regime)
        
        # Extract SPX specific properties for back-compatibility
        spx_mlp = mlp_state.get("spx", {})
        mlp_prob = spx_mlp.get("bull_probability", 0.5)

        
        mcs, sub_comps = compute_mcs(self.clean_daily, self.bonds, self.clean_daily)
        self.snapshot.mcs = {"score": mcs, "label": "NEUTRAL", "components": sub_comps}
        
        prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "market_snapshot_prior.json")
        prior = {}
        if os.path.exists(prior_path):
            try:
                with open(prior_path, 'r') as f:
                    prior = json.load(f)
            except: pass
            
        prior_regime = prior.get("regime", {}).get("dominant_regime")
        regime_changed = current_regime != prior_regime
        now_utc = datetime.now(timezone.utc)
        prior_start_str = prior.get("regime", {}).get("start_utc", now_utc.isoformat())
        prior_start = datetime.fromisoformat(prior_start_str)
        if prior_start.tzinfo is None:
            prior_start = prior_start.replace(tzinfo=timezone.utc)
        
        if regime_changed:
            duration_days = 0.0
            start_utc_str = now_utc.isoformat()
        else:
            duration_days = (now_utc - prior_start).total_seconds() / 86400.0
            start_utc_str = prior_start_str
            
        self.snapshot.regime = RegimeState(
            current=current_regime,
            dominant_regime=current_regime,
            tactical_alpha_regime=hmm_alpha_dom,
            probabilities=hmm_beta_probs or {},
            tactical_alpha_probabilities=hmm_alpha_probs or {},
            transition_risk=tr_risk,
            start_utc=start_utc_str,
            duration_days=duration_days
        )
        
        prior_state = prior.get("kalman_state", {}).get("probabilities")
        prior_cov = prior.get("kalman_state", {}).get("covariance_matrix")
        
        # v4.9.0 GARCH Bayesian Updating
        spx_garch_regime = getattr(self, 'garch_layer', {}).get("SPX", {}).get("regime", "NORMAL")
        if spx_garch_regime == "ELEVATED" and hmm_beta_probs:
            risk_on_keys = ["LIQUIDITY_DRIVEN_RALLY", "RISK_ON_EXPANSION"]
            for k in risk_on_keys:
                if k in hmm_beta_probs and hmm_beta_probs[k] > 0:
                    penalty = hmm_beta_probs[k] * 0.5
                    hmm_beta_probs[k] -= penalty
                    hmm_beta_probs["NEUTRAL_TRANSITIONAL"] = hmm_beta_probs.get("NEUTRAL_TRANSITIONAL", 0.0) + penalty
                    
        kalman_res = self.risk_engine.run_kalman_filter(mcs, sub_comps, hmm_beta_probs or {}, prior_state, prior_cov)
        
        tvd_score = 0.0
        if spx_mlp and hmm_beta_probs:
            tvd_score = calculate_model_tvd(hmm_beta_probs, spx_mlp)
        kalman_res.tvd = tvd_score
        
        entropy = self.risk_engine.compute_shannon_entropy(np.array(list((hmm_beta_probs or {}).values())))
        half_life = 99.0
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "tuning_configs.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                t_conf = json.load(f)
                half_life = t_conf.get("regime_half_lives", {}).get(current_regime, 99.0)
                
        current_spx_val = self.clean_daily.get("SPX", {}).get("current", 0.0) if self.clean_daily.get("SPX") else 0.0
        
        is_downtrend = False
        if self._spx_raw_series is not None and len(self._spx_raw_series) >= 20:
            ema_20 = float(self._spx_raw_series.ewm(span=20, adjust=False).mean().iloc[-1])
            is_downtrend = float(current_spx_val) < ema_20
        
        current_ihi = self.clean_daily.get("volume_activity_heat", {}).get("institutional_heat_index", 0.0)
        
        predictions_history_path = os.path.join(os.path.dirname(__file__), "..", "data", "predictions", f"mlp_predictions_history_{self.interval}.json")
        brier_score = 0.1500
        history = []
        try:
            if os.path.exists(predictions_history_path):
                with open(predictions_history_path, 'r') as f:
                    history = json.load(f)
            brier_score, history = run_self_calibration(history, current_spx_val, current_ihi, grading_delay=5, interval=self.interval)
            
            history.append({
                "predicted_risk_on": mlp_prob,
                "spx_val_at_prediction": current_spx_val,
                "target_graded": False
            })
            with open(predictions_history_path, 'w') as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            logger.error(f"Failed self-calibration: {e}")
            
        kalman_res.brier_score_calibration = brier_score

        spx_ret_z = self.clean_daily.get("SPX", {}).get("z_score", 0.0) if self.clean_daily.get("SPX") else 0.0
        is_capitulation_override = False
        if spx_ret_z < -1.5 and spx_ret_z >= -3.0 and current_ihi > 0.0 and mlp_prob > 0.5:
            is_capitulation_override = True

        is_momentum_override = False
        if spx_ret_z > 1.0 and current_ihi > 0.1 and 0.4 < mlp_prob <= 0.80:
            is_momentum_override = True

        is_black_swan = False
        if spx_ret_z < -3.5:
            is_black_swan = True
            
        is_bull_trap = False
        if spx_ret_z > 2.0 and self.clean_daily.get("VIX", {}).get("current", 0) > 25:
            is_bull_trap = True

        # --- Sizing: RL Agent or Kelly (feature-flagged) ---
        kelly = None
        if self.use_rl_agent and self.rl_agent and self.rl_agent.is_loaded():
            current_allocs = {k.lower().replace("_kelly", ""): v 
                              for k, v in self.snapshot.data_science_layer.get(
                                  "target_allocations", {}).items()}
            kelly = self.rl_agent.predict_allocations(
                features_vector=self.features_vector,
                current_allocations=current_allocs
            )
            
        if kelly is None:
            kelly = self.risk_engine.compute_multi_asset_kelly(
                mlp_predictions=mlp_state,
                dominant_state=kalman_res.dominant_state,
                brier_score=brier_score,
                duration_days=duration_days,
                is_capitulation_override=is_capitulation_override,
                is_momentum_override=is_momentum_override,
                is_black_swan=is_black_swan,
                is_bull_trap=is_bull_trap,
                hmm_regime=self.snapshot.regime.current,
                current_ihi=current_ihi,
                is_downtrend=is_downtrend,
                max_kelly_cap=0.30 if self.interval == "4h" else 0.40,
                equity_drawdown=self.paper_broker.get_equity_drawdown()
            )

        # --- Multi-Timeframe Entry Gating (4H and 1D only) ---
        if self.interval in ("4h", "1d") and os.path.exists(self.entry_quality_path):
            try:
                with open(self.entry_quality_path, "r") as f:
                    entry_quality = json.load(f)

                computed_at = datetime.fromisoformat(entry_quality.get("computed_utc", "2000-01-01T00:00:00+00:00"))
                age_hours = (datetime.now(timezone.utc) - computed_at).total_seconds() / 3600.0

                if age_hours <= 5.0:
                    entry_score = float(entry_quality.get("entry_score", 0.5))
                    entry_bias  = entry_quality.get("entry_bias", "FLAT")

                    if entry_score < 0.20:
                        logger.warning(f"MTF Entry Gate: score {entry_score:.2f} below 0.20 floor. Zeroing long Kelly.")
                        for k in kelly:
                            if k not in ["Short_Kelly", "Cash"]: kelly[k] = 0.0
                    elif entry_score < 0.35:
                        logger.info(f"MTF Entry Gate: score {entry_score:.2f} below 0.35. Halving long Kelly.")
                        for k in kelly:
                            if k not in ["Short_Kelly", "Cash"]: kelly[k] = round(kelly[k] * 0.5, 3)
                    else:
                        logger.info(f"MTF Entry Gate: score {entry_score:.2f} — no adjustment.")

                    if entry_bias == "SHORT" and kelly.get("SPX_Kelly", 0.0) > 0:
                        logger.info("MTF bias conflict: 1H SHORT, 4H LONG. Applying 0.70x long discount.")
                        kelly["SPX_Kelly"] = round(kelly["SPX_Kelly"] * 0.70, 3)
                else:
                    logger.warning(f"Entry quality score is stale ({age_hours:.1f}h old). Skipping MTF gate.")
            except Exception as e:
                logger.error(f"MTF entry gate failed: {e}")
                
        self.snapshot.kalman_state = kalman_res
        self.snapshot.mlp_deep_state = mlp_state or {}
        self.snapshot.data_science_layer = {
            "ordered_features_list": [lbl for lbl, _, _ in self.ordered_feature_keys],
            "features_vector": self.features_vector,
            "features_dict": self.feature_metadata,
            "epistemic_metrics": {
                "shannon_entropy": entropy,
                "kelly_exposure_fraction": kelly,
                "is_high_risk_edge": bool(kalman_res.dominant_prob >= 0.45),
                "is_capitulation_override_active": is_capitulation_override
            }
        }
        
        self.event_bus.publish("EnginesCompleted", {})

    def handle_engines_completed(self, payload):
        # --- Entry Quality Scoring (1H only) ---
        if self.interval == "1h" and hasattr(self, 'raw_hourly_data'):
            spx_1h_close = self.raw_hourly_data["^GSPC"]["Close"].dropna() if "^GSPC" in self.raw_hourly_data.columns.levels[0] else pd.Series()
            spx_1h_vol   = self.raw_hourly_data["^GSPC"]["Volume"].dropna() if "^GSPC" in self.raw_hourly_data.columns.levels[0] else pd.Series()
            spx_1h_high  = self.raw_hourly_data["^GSPC"]["High"].dropna()   if "^GSPC" in self.raw_hourly_data.columns.levels[0] else pd.Series()
            spx_1h_low   = self.raw_hourly_data["^GSPC"]["Low"].dropna()    if "^GSPC" in self.raw_hourly_data.columns.levels[0] else pd.Series()
            vix_1h       = self.raw_hourly_data["^VIX"]["Close"].dropna()   if "^VIX" in self.raw_hourly_data.columns.levels[0] else pd.Series()

            entry_result = self.entry_engine.score_entry(
                spx_close_1h=spx_1h_close,
                spx_vol_1h=spx_1h_vol,
                spx_high_1h=spx_1h_high,
                spx_low_1h=spx_1h_low,
                vix_1h=vix_1h,
                dominant_regime=self.snapshot.regime.current,
                kalman_dominant_state=self.snapshot.kalman_state.dominant_state
            )
            entry_result["computed_utc"] = datetime.now(timezone.utc).isoformat()
            entry_result["interval_used"] = "1h"

            with open(self.entry_quality_path, "w") as f:
                json.dump(entry_result, f, indent=4)
            logger.info(f"Entry quality score computed: {entry_result['entry_score']:.2f} ({entry_result['entry_bias']})")

        headlines = fetch_rss_headlines()
        
        # Prepare inputs for experts
        calendar_events = self.snapshot.economic_calendar.events
        spread_2s10s = self.snapshot.bonds.get("spread_2s10s", 0.0)
        vix_zscore = self.snapshot.market_extremes_insight.temperature_zscore
        volume_heat = self.clean_daily.get("volume_activity_heat", {}).get("institutional_heat_index", 0.0)
        
        def run_llm():
            # Prevent 429 quota exhaustion: skip LLM macro for 1h intervals and use cached state
            if getattr(self, "interval", "") == "1h":
                prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "market_snapshot.json")
                if os.path.exists(prior_path):
                    try:
                        with open(prior_path, 'r') as f:
                            prior_data = json.load(f)
                            if prior_data and "news_signal" in prior_data and prior_data["news_signal"]:
                                logger.info("Using cached LLM Macro from previous run to save Gemini API quota.")
                                prior_sig = prior_data["news_signal"]
                                return {
                                    "fed_policy_hawkishness_prob": prior_sig.get("fed_policy_hawkishness_prob", 0.5),
                                    "fear_greed_sentiment_score": prior_sig.get("fear_greed_sentiment_score", 0.5),
                                    "quantitative_divergence_flag": prior_sig.get("quantitative_divergence_flag", False),
                                    "reasoning": prior_sig.get("reasoning", "Cached from previous run.")
                                }
                    except Exception as e:
                        logger.warning(f"Failed to load cached macro: {e}")
            return self.gemini_adapter.run_llm_macro(headlines, calendar_events, spread_2s10s, vix_zscore, volume_heat)

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            llm_future = executor.submit(run_llm)
            llm_res = llm_future.result()
            
        news_res = self.consensus_engine.synthesize(llm_res, self.snapshot.regime.current)
        self.snapshot.news_signal = news_res
        
        # Override kelly if global macro sentiment is extreme or there's divergence
        sentiment = self.snapshot.news_signal.conviction
        signal = self.snapshot.news_signal.signal
        regime = self.snapshot.regime.current
        divergence = self.snapshot.news_signal.quantitative_divergence_flag
        
        multiplier = 1.0
        if divergence:
            logger.warning("Quantitative divergence flagged by LLM. Slashing multiplier to 0.5.")
            multiplier = min(multiplier, 0.5)
        elif signal == "SHORT":
            multiplier = min(multiplier, 0.5)
        elif signal == "MIXED":
            multiplier = min(multiplier, 0.75)
            logger.info("Mixed macro signals detected. Applying 0.75x Kelly discount.")
            
        current_kelly = self.snapshot.data_science_layer["epistemic_metrics"]["kelly_exposure_fraction"]
        if multiplier != 1.0:
            if isinstance(current_kelly, dict):
                long_keys = ["SPX_Kelly", "BTC_Kelly", "NVDA_Kelly", "TSLA_Kelly", "DELL_Kelly", "SPCE_Kelly", "WTI_Kelly"]
                for k in long_keys:
                    if k in current_kelly:
                        current_kelly[k] = round(current_kelly[k] * multiplier, 3)
            else:
                new_kelly = round(min(1.2, current_kelly * multiplier), 3)
                self.snapshot.data_science_layer["epistemic_metrics"]["kelly_exposure_fraction"] = new_kelly
        
        spx_ret_now = self.clean_daily.get("SPX", {}).get("delta_pct", 0.0) if self.clean_daily.get("SPX") else 0.0
        escalation = "ROUTINE"
        if spx_ret_now and abs(spx_ret_now) > 2.0: escalation = "CRITICAL"
        elif spx_ret_now and abs(spx_ret_now) > 1.0: escalation = "ELEVATED"
        
        if self.snapshot.kalman_state.tvd > 0.10 and escalation == "ROUTINE":
            escalation = "ELEVATED"
            
        self.snapshot.data_driven_escalation = escalation
        self.snapshot.raw_indicators = self.clean_daily
        self.snapshot.bonds = self.bonds
        self.snapshot.generated_utc = datetime.now(timezone.utc).isoformat()
        
        self.event_bus.publish("PipelineComplete", self.snapshot)

    def handle_pipeline_complete(self, snapshot_payload):
        out_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "market_snapshot.json")
        prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "state", "market_snapshot_prior.json")
        telemetry_path = os.path.join(os.path.dirname(__file__), "..", "data", "telemetry", "live_telemetry.json")
        
        snapshot_dict = self.snapshot.model_dump()
        
        with open(out_path, 'w') as f:
            json.dump(snapshot_dict, f, indent=4)
            
        # Write Phase 2 Live Telemetry File
        kelly_obj = self.snapshot.data_science_layer.get("epistemic_metrics", {}).get("kelly_exposure_fraction", {})
        if not isinstance(kelly_obj, dict):
            kelly_obj = {"SPX_Kelly": kelly_obj, "GLD_Kelly": 0.0}
            
        entry_quality = {}
        if os.path.exists(self.entry_quality_path):
            try:
                with open(self.entry_quality_path, "r") as f:
                    entry_quality = json.load(f)
            except Exception:
                pass
                
        telemetry_payload = {
            "timestamp_utc": self.snapshot.generated_utc,
            "dominant_regime": self.snapshot.regime.dominant_regime,
            "spx_kelly_fraction": kelly_obj.get("SPX_Kelly", 0.0),
            "safe_haven_kelly_fraction": kelly_obj.get("GLD_Kelly", 0.0),
            "is_capitulation_override_active": self.snapshot.data_science_layer.get("epistemic_metrics", {}).get("is_capitulation_override_active", False),
            "institutional_heat_index": self.snapshot.raw_indicators.get("volume_activity_heat", {}).get("institutional_heat_index", 0.0),
            "entry_quality_score": entry_quality.get("entry_score", None) if entry_quality else None,
            "entry_bias": entry_quality.get("entry_bias", "FLAT") if entry_quality else "FLAT"
        }
        
        with open(telemetry_path, 'w') as f:
            json.dump(telemetry_payload, f, indent=4)
            
        self.lake_manager.save_unstructured(snapshot_dict, "market_snapshot.jsonl")
        
        # Execute Rebalance in Paper Trading
        self.bar_count += 1
        bars_since_rebalance = self.bar_count - self.last_rebalance_bar
        should_rebalance = bars_since_rebalance >= self.MIN_HOLD_BARS
        
        try:
            if should_rebalance:
                target_allocs = {
                    "SPX":   kelly_obj.get("SPX_Kelly", 0.0),
                    "Short": kelly_obj.get("Short_Kelly", 0.0),
                    "Gold":  kelly_obj.get("GLD_Kelly", 0.0),
                    "BTC":   kelly_obj.get("BTC_Kelly", 0.0),
                    "WTI":   kelly_obj.get("WTI_Kelly", 0.0),
                    "NVDA":  kelly_obj.get("NVDA_Kelly", 0.0),
                    "TSLA":  kelly_obj.get("TSLA_Kelly", 0.0),
                    "DELL":  kelly_obj.get("DELL_Kelly", 0.0),
                    "SPCE":  kelly_obj.get("SPCE_Kelly", 0.0)
                }
                current_prices = {
                    "SPX":   self.clean_daily.get("SPX",   {}).get("current", 0.0),
                    "Short": self.clean_daily.get("SH",    {}).get("current", 0.0),
                    "Gold":  self.clean_daily.get("Gold",  {}).get("current", 0.0),
                    "BTC":   self.clean_daily.get("BTC",   {}).get("current", 0.0),
                    "WTI":   self.clean_daily.get("WTI",   {}).get("current", 0.0),
                    "NVDA":  self.clean_daily.get("NVDA",  {}).get("current", 0.0),
                    "TSLA":  self.clean_daily.get("TSLA",  {}).get("current", 0.0),
                    "DELL":  self.clean_daily.get("DELL",  {}).get("current", 0.0),
                    "SPCE":  self.clean_daily.get("SPCE",  {}).get("current", 0.0)
                }
                self.paper_broker.execute_rebalance(target_allocs, current_prices, vix_zscore=self.snapshot.market_extremes_insight.temperature_zscore, hmm_regime=self.snapshot.regime.current)
                self.last_rebalance_bar = self.bar_count
                logger.info(f"Rebalance executed at bar {self.bar_count}.")
            else:
                logger.info(f"Minimum hold period active. {bars_since_rebalance}/{self.MIN_HOLD_BARS} bars since last rebalance. Skipping.")
        except Exception as e:
            logger.error(f"Paper Execution failed: {e}")
            
        # --- Regime-Adaptive Frequency Recommendation ---
        try:
            entropy = self.snapshot.data_science_layer.get("epistemic_metrics", {}).get("shannon_entropy", 1.58)
            vix_z = float(self.snapshot.market_extremes_insight.temperature_zscore)
            brier = float(self.snapshot.kalman_state.brier_score_calibration) if self.snapshot.kalman_state else 0.15
            duration = float(self.snapshot.regime.duration_days)

            freq_result = self.frequency_controller.evaluate(
                shannon_entropy=entropy,
                vix_zscore=vix_z,
                dominant_regime=self.snapshot.regime.current,
                brier_score=brier,
                duration_days=duration,
                kalman_dominant_state=self.snapshot.kalman_state.dominant_state if self.snapshot.kalman_state else "neutral",
                kalman_is_ambiguous=self.snapshot.kalman_state.is_ambiguous if self.snapshot.kalman_state else True
            )
            freq_result["evaluated_utc"] = datetime.now(timezone.utc).isoformat()

            with open(self.frequency_state_path, "w") as f:
                json.dump(freq_result, f, indent=4)
            logger.info(f"FrequencyController: recommended={freq_result['recommended_frequency']} (score={freq_result['score']}). {freq_result['reason']}")
        except Exception as e:
            logger.error(f"FrequencyController evaluation failed: {e}")

        logger.info("v6.0.0 Real-Time Event-Driven Pipeline Complete")
            
        with open(prior_path, 'w') as f:
            json.dump(snapshot_dict, f, indent=4)
            


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", choices=["1d", "1wk", "1h", "4h"])
    parser.add_argument("--use-1h-context", action="store_true", help="Bypass HMM and load latest 1H context")
    args = parser.parse_args()
    
    conductor = Conductor(interval=args.interval, use_1h_context=args.use_1h_context)
    conductor.run()
