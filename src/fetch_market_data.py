import os
import json
import argparse
import traceback
import feedparser
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.observability.logger import get_logger
from src.observability.event_bus import EventBus
from src.data_lake.lake_manager import LakeManager
from src.adapters.yahoo_adapter import YahooAdapter
from src.adapters.gemini_adapter import GeminiAdapter
from src.adapters.groq_adapter import GroqAdapter
from src.adapters.forexfactory_adapter import ForexFactoryAdapter
from src.adapters.paper_broker import PaperBroker
from src.engines.hmm_engine import HMMEngine
from src.engines.risk_engine import RiskEngine
from src.engines.consensus_engine import ConsensusEngine
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
    def __init__(self, interval="1d"):
        self.interval = interval
        logger.info(f"Initializing v5.2.0 Event-Driven Conductor (Interval: {interval})")
        
        self.lake_manager = LakeManager()
        self.event_bus = EventBus()
        self.event_bus.set_interceptor(self.lake_manager.log_event)
        self.paper_broker = PaperBroker(os.path.join(os.path.dirname(__file__), "..", "data"))
        
        fred_key = get_fred_key()
        self.data_broker = YahooAdapter(fred_key=fred_key)
        self.ff_adapter = ForexFactoryAdapter()
        self.gemini_adapter = GeminiAdapter()
        self.groq_adapter = GroqAdapter()
        
        hmm_model_path = os.path.join(os.path.dirname(__file__), '..', 'models', f'hmm_model_{self.interval}.pkl')
        if not os.path.exists(hmm_model_path) and self.interval == "1d":
            hmm_model_path = None
        self.hmm_engine = HMMEngine(model_path=hmm_model_path)
        self.risk_engine = RiskEngine()
        self.consensus_engine = ConsensusEngine()
        
        self.snapshot = MarketSnapshot()
        
        self.clean_daily = {}
        self.bonds = {}
        self.features_vector = []
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
            ("usdcad_ret", "USDCAD", "delta_pct"),
            ("es_ret", "ES", "delta_pct"),
            ("nq_ret", "NQ", "delta_pct"),
            ("ym_ret", "YM", "delta_pct"),
            ("rty_ret", "RTY", "delta_pct")
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
        raw_daily_data = self.data_broker.fetch_ohlcv_daily(tickers, period="90d", interval=self.interval)
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
        
        self.clean_daily = clean_daily
        self.bonds = bonds
        
        # GARCH & Extremes
        garch_layer = {}
        for name, ticker in garch_targets.items():
            cond_vol, regime, f_vol = compute_garch_volatility(ticker)
            garch_layer[name] = {"conditional_vol": cond_vol if cond_vol else 0.0, "regime": regime}
            
        self.garch_layer = garch_layer
            
        spx_s = parsed_daily.get("SPX", {}).get("raw_series")
        vix_s = parsed_daily.get("VIX", {}).get("raw_series")
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
        hmm_beta_probs, hmm_beta_dom, tr_risk, _ = self.hmm_engine.run_inference(self.features_vector)
        hmm_alpha_probs, hmm_alpha_dom, _, _ = self.hmm_engine.run_inference(self.features_vector)
        
        current_regime = hmm_beta_dom if hmm_beta_dom else "NEUTRAL_TRANSITIONAL"
        
        mlp_packages = load_mlp_models(self.interval)
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
        if mlp_prob > 0.80:
            is_bull_trap = True

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
            current_ihi=current_ihi
        )

        
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
        headlines = fetch_rss_headlines()
        
        # Prepare inputs for experts
        calendar_events = self.snapshot.economic_calendar.events
        spread_2s10s = self.snapshot.bonds.get("2s10s_spread", 0.0)
        vix_zscore = self.snapshot.market_extremes_insight.temperature_zscore
        volume_heat = self.snapshot.data_science_layer.get("advanced_metrics", {}).get("volume_activity_heat", 0.0)
        
        import concurrent.futures
        
        def run_macro():
            res = self.groq_adapter.run_macro_policy_expert(headlines, calendar_events, spread_2s10s)
            if "Error:" in res.get("reasoning", "") or "Default fallback" in res.get("reasoning", ""):
                res = self.gemini_adapter.run_macro_policy_expert(headlines, calendar_events, spread_2s10s)
                res["reasoning"] = "(Failover to Gemini) " + res.get("reasoning", "")
            return res
            
        def run_psych():
            res = self.gemini_adapter.run_market_psychology_expert(headlines, vix_zscore, volume_heat)
            if "Error:" in res.get("reasoning", "") or "Default fallback" in res.get("reasoning", ""):
                res = self.groq_adapter.run_market_psychology_expert(headlines, vix_zscore, volume_heat)
                res["reasoning"] = "(Failover to Groq) " + res.get("reasoning", "")
            return res

        with concurrent.futures.ThreadPoolExecutor() as executor:
            macro_future = executor.submit(run_macro)
            psych_future = executor.submit(run_psych)
            
            macro_res = macro_future.result()
            psych_res = psych_future.result()
            
        # Track providers to detect parallel LLM Echo Chamber
        macro_provider = "Groq"
        if "(Failover to Gemini)" in macro_res.get("reasoning", "") or "Default fallback" in macro_res.get("reasoning", ""):
            macro_provider = "Gemini"
            
        psych_provider = "Gemini"
        if "(Failover to Groq)" in psych_res.get("reasoning", "") or "Default fallback" in psych_res.get("reasoning", ""):
            psych_provider = "Groq"
            
        echo_chamber = (macro_provider == psych_provider)
        
        news_res = self.consensus_engine.synthesize(macro_res, psych_res, self.snapshot.regime.current, echo_chamber=echo_chamber)
        self.snapshot.news_signal = news_res
        
        # Override kelly if global macro sentiment is extreme or there's divergence
        sentiment = self.snapshot.news_signal.conviction
        signal = self.snapshot.news_signal.signal
        regime = self.snapshot.regime.current
        divergence = self.snapshot.news_signal.quantitative_divergence_flag
        
        multiplier = 1.0
        if divergence:
            multiplier = 0.5
        elif signal == "LONG" and sentiment >= 0.75 and regime == "RISK_ON_EXPANSION":
            multiplier = 1.2
        elif signal == "SHORT":
            multiplier = 0.5
            
        current_kelly = self.snapshot.data_science_layer["epistemic_metrics"]["kelly_exposure_fraction"]
        if multiplier != 1.0:
            if isinstance(current_kelly, dict):
                new_spx_kelly = round(min(1.2, current_kelly.get("SPX_Kelly", 0.0) * multiplier), 3)
                self.snapshot.data_science_layer["epistemic_metrics"]["kelly_exposure_fraction"]["SPX_Kelly"] = new_spx_kelly
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
            
        telemetry_payload = {
            "timestamp_utc": self.snapshot.generated_utc,
            "dominant_regime": self.snapshot.regime.dominant_regime,
            "spx_kelly_fraction": kelly_obj.get("SPX_Kelly", 0.0),
            "safe_haven_kelly_fraction": kelly_obj.get("GLD_Kelly", 0.0),
            "is_capitulation_override_active": self.snapshot.data_science_layer.get("epistemic_metrics", {}).get("is_capitulation_override_active", False),
            "institutional_heat_index": self.snapshot.raw_indicators.get("volume_activity_heat", {}).get("institutional_heat_index", 0.0)
        }
        
        with open(telemetry_path, 'w') as f:
            json.dump(telemetry_payload, f, indent=4)
            
        self.lake_manager.save_unstructured(snapshot_dict, "market_snapshot.jsonl")
        
        # Execute paper trading simulation
        try:
            target_allocs = {
                "SPX": kelly_obj.get("SPX_Kelly", 0.0),
                "Gold": kelly_obj.get("GLD_Kelly", 0.0)
            }
            current_prices = {
                "SPX": self.clean_daily.get("SPX", {}).get("current", 0.0),
                "Gold": self.clean_daily.get("Gold", {}).get("current", 0.0)
            }
            self.paper_broker.execute_rebalance(target_allocs, current_prices)
        except Exception as e:
            logger.error(f"Paper broker execution failed: {e}")
            
        with open(prior_path, 'w') as f:
            json.dump(snapshot_dict, f, indent=4)
            
        logger.info("v5.2.0 Event-Driven Pipeline Complete")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=str, default="1d", choices=["1d", "1wk", "1h", "4h"])
    args = parser.parse_args()
    
    conductor = Conductor(interval=args.interval)
    conductor.run()
