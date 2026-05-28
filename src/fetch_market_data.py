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
from src.engines.hmm_engine import HMMEngine
from src.engines.risk_engine import RiskEngine
from src.schemas.models import MarketSnapshot, RegimeState, MarketExtremes, NewsSignal, KalmanState
from src.engines.feature_engine import (
    ALL_YF_TICKERS, get_fred_key, get_signature_salt, sign_snapshot_payload,
    check_mathematical_consistency, append_to_immutable_chain,
    compute_stats, compute_volume_heat, compute_market_extremes,
    compute_garch_volatility, load_mlp_model, run_mlp_inference,
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
    def __init__(self):
        logger.info("Initializing v4.7.0 Event-Driven Conductor")
        self.event_bus = EventBus()
        self.lake_manager = LakeManager()
        self.event_bus.set_interceptor(self.lake_manager.log_event)
        
        fred_key = get_fred_key()
        self.data_broker = YahooAdapter(fred_key=fred_key)
        self.llm_provider = GeminiAdapter()
        
        self.hmm_engine = HMMEngine()
        self.risk_engine = RiskEngine()
        
        self.snapshot = MarketSnapshot()
        
        self.clean_daily = {}
        self.bonds = {}
        self.features_vector = []
        self.feature_metadata = {}
        self.ordered_feature_keys = [
            ("SPX_ret", "SPX", "delta_pct"),
            ("DXY_ret", "DXY", "delta_pct"),
            ("VIX_zscore", "VIX", "z_score"),
            ("WTI_ret", "WTI", "delta_pct"),
            ("GoldSilverRatio_ret", "gold_to_silver_ratio", "delta_pct"),
            ("US10Y_delta", "bonds", "delta"),
            ("US_2s10s_spread", "bonds", "spread_2s10s"),
            ("CryptoMFI_zscore", "institutional_crypto_mfi", "composite_z"),
            ("VolumeHeat_ihi", "volume_activity_heat", "institutional_heat_index"),
            ("USDCAD_ret", "USDCAD", "delta_pct")
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
        logger.info("Starting Data Ingestion Phase via Event Bus")
        tickers = list(ALL_YF_TICKERS.values())
        raw_daily_data = self.data_broker.fetch_ohlcv_daily(tickers, period="30d")
        raw_hourly_data = self.data_broker.fetch_ohlcv_hourly(tickers, period="5d")
        
        self.lake_manager.save_tabular(raw_daily_data, "raw_daily_ohlcv.parquet")
        self.lake_manager.save_tabular(raw_hourly_data, "raw_hourly_ohlcv.parquet")
        
        self.event_bus.publish("DataFetched", {"daily": raw_daily_data, "hourly": raw_hourly_data})

    def handle_data_fetched(self, payload):
        raw_daily_data = payload["daily"]
        raw_hourly_data = payload["hourly"]
        
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
            
        bonds = {
            "US2Y": {"current": self.data_broker.fetch_yield("DGS2")},
            "US10Y": {"current": self.data_broker.fetch_yield("DGS10")}
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
            garch_layer[name] = {"conditional_vol": cond_vol if cond_vol else 0.0}
            
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
                    if key == "delta" and bonds.get("US10Y"): val = bonds["US10Y"].get("delta", 0.0)
                    elif key == "spread_2s10s": val = bonds.get("spread_2s10s", 0.0)
                else: val = self.clean_daily.get(category, {}).get(key, 0.0)
                if val is None: val = 0.0
            except Exception: pass
            self.features_vector.append(float(val))
            self.feature_metadata[label] = float(val)
            
        self.event_bus.publish("FeaturesEngineered", {"vector": self.features_vector, "meta": self.feature_metadata})

    def handle_features_engineered(self, payload):
        mlp_package = load_mlp_model()
        mlp_state = run_mlp_inference(self.features_vector, mlp_package)
        
        mcs, sub_comps = compute_mcs(self.clean_daily, self.bonds, self.clean_daily)
        self.snapshot.mcs = {"score": mcs, "label": "NEUTRAL", "components": sub_comps}
        
        hmm_beta_probs, hmm_beta_dom, tr_risk, _ = self.hmm_engine.run_inference(self.features_vector)
        hmm_alpha_probs, hmm_alpha_dom, _, _ = self.hmm_engine.run_inference(self.features_vector)
        
        current_regime = hmm_beta_dom if hmm_beta_dom else "NEUTRAL_TRANSITIONAL"
        
        prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "market_snapshot_prior.json")
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
        
        kalman_res = self.risk_engine.run_kalman_filter(mcs, sub_comps, hmm_beta_probs or {}, prior_state, prior_cov)
        
        tvd_score = 0.0
        if mlp_state and hmm_beta_probs:
            tvd_score = calculate_model_tvd(hmm_beta_probs, mlp_state)
        kalman_res.tvd = tvd_score
        
        entropy = self.risk_engine.compute_shannon_entropy(np.array(list((hmm_beta_probs or {}).values())))
        half_life = 99.0
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "tuning_configs.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                t_conf = json.load(f)
                half_life = t_conf.get("regime_half_lives", {}).get(current_regime, 99.0)
                
        kelly = self.risk_engine.compute_kelly_sizing(kalman_res.dominant_prob, 0.1, duration_days, half_life)
        
        spx_ret_now = self.clean_daily.get("SPX", {}).get("delta_pct", 0.0) if self.clean_daily.get("SPX") else 0.0
        predictions_history_path = os.path.join(os.path.dirname(__file__), "..", "data", "mlp_predictions_history.json")
        brier_score = 0.1500
        try:
            from src.fetch_market_data_legacy import run_self_calibration
            brier_score, _ = run_self_calibration(spx_ret_now, predictions_history_path)
        except: pass
        kalman_res.brier_score_calibration = brier_score
        
        self.snapshot.kalman_state = kalman_res
        self.snapshot.mlp_deep_state = mlp_state or {}
        self.snapshot.data_science_layer = {
            "ordered_features_list": [lbl for lbl, _, _ in self.ordered_feature_keys],
            "features_vector": self.features_vector,
            "features_dict": self.feature_metadata,
            "epistemic_metrics": {
                "shannon_entropy": entropy,
                "kelly_exposure_fraction": kelly,
                "is_high_risk_edge": bool(kalman_res.dominant_prob >= 0.45)
            }
        }
        
        self.event_bus.publish("EnginesCompleted", {})

    def handle_engines_completed(self, payload):
        headlines = fetch_rss_headlines()
        news_res = self.llm_provider.parse_news(headlines, market_data=self.feature_metadata)
        self.snapshot.news_signal = news_res
        
        # Override kelly if global macro sentiment is extreme
        sentiment = self.snapshot.news_signal.conviction
        signal = self.snapshot.news_signal.signal
        regime = self.snapshot.regime.current
        
        multiplier = 1.0
        if signal == "LONG" and sentiment >= 0.75 and regime == "RISK_ON_EXPANSION":
            multiplier = 1.2
        elif signal == "SHORT":
            multiplier = 0.5
            
        current_kelly = self.snapshot.data_science_layer["epistemic_metrics"]["kelly_exposure_fraction"]
        if multiplier != 1.0:
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
        out_path = os.path.join(os.path.dirname(__file__), "..", "data", "market_snapshot.json")
        prior_path = os.path.join(os.path.dirname(__file__), "..", "data", "market_snapshot_prior.json")
        
        snapshot_dict = self.snapshot.model_dump()
        
        with open(out_path, 'w') as f:
            json.dump(snapshot_dict, f, indent=4)
            
        self.lake_manager.save_unstructured(snapshot_dict, "market_snapshot.jsonl")
        
        with open(prior_path, 'w') as f:
            json.dump(snapshot_dict, f, indent=4)
            
        logger.info("v4.7.0 Event-Driven Pipeline Complete")

def main():
    conductor = Conductor()
    conductor.run()

if __name__ == "__main__":
    main()
