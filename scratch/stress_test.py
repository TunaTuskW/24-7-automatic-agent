"""
QuantOS Stress Test Suite
=========================
Run: PYTHONPATH=. python3 scratch/stress_test.py
Tests 12 edge cases across EntryEngine, FrequencyController,
MarketEventDetector, RiskEngine, and the Backtester date interface.
"""

import sys
import os
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

results = []

def run_test(name, fn):
    try:
        outcome = fn()
        status = outcome.get("status", "FAIL")
        detail = outcome.get("detail", "")
        label = PASS if status == "PASS" else (WARN if status == "WARN" else FAIL)
        print(f"[{label}] {name}")
        if detail:
            print(f"       {detail}")
        results.append((name, status, detail))
    except Exception as e:
        msg = traceback.format_exc().strip().split("\n")[-1]
        print(f"[{FAIL}] {name}")
        print(f"       EXCEPTION: {msg}")
        results.append((name, "FAIL", f"Unhandled exception: {msg}"))

def make_flat_series(length=50, value=5000.0):
    idx = pd.date_range("2024-01-01", periods=length, freq="h")
    return pd.Series([value] * length, index=idx)

def make_nan_series(length=80):
    idx = pd.date_range("2024-01-01", periods=length, freq="h")
    data = [np.nan if i % 7 == 0 else 5000 + i for i in range(length)]
    return pd.Series(data, index=idx)

def make_normal_close(length=80, start=5000.0, seed=42):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.005, length)
    prices = start * np.cumprod(1 + returns)
    idx = pd.date_range("2024-01-01", periods=length, freq="h")
    return pd.Series(prices, index=idx)

def make_volume_series(length=80, seed=42):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.integers(1_000_000, 5_000_000, length).astype(float),
                     index=pd.date_range("2024-01-01", periods=length, freq="h"))


def test_01_entry_engine_flat_price():
    from src.engines.entry_engine import EntryEngine
    engine = EntryEngine()
    flat = make_flat_series(50)
    result = engine.score_entry(
        spx_close_1h=flat, spx_vol_1h=make_volume_series(50),
        spx_high_1h=flat, spx_low_1h=flat,
        vix_1h=pd.Series([20.0] * 50),
        dominant_regime="RISK_ON_EXPANSION", kalman_dominant_state="risk_on"
    )
    if result.get("entry_score") is None or pd.isna(result["entry_score"]):
        return {"status": "FAIL", "detail": "entry_score is None/NaN on flat price series"}
    if result["entry_score"] == 0.5 and result["entry_bias"] == "FLAT":
        return {"status": "WARN", "detail": f"Flat price: default 0.5/FLAT returned. "
                "volume_confirmation=0 because bar_range=0. Acceptable but add explicit zero-variance guard."}
    return {"status": "PASS", "detail": f"score={result['entry_score']}, bias={result['entry_bias']}"}


def test_02_entry_engine_nan_series():
    from src.engines.entry_engine import EntryEngine
    engine = EntryEngine()
    nan_close = make_nan_series(80)
    try:
        result = engine.score_entry(
            spx_close_1h=nan_close, spx_vol_1h=make_nan_series(80),
            spx_high_1h=nan_close, spx_low_1h=nan_close,
            vix_1h=nan_close,
            dominant_regime="NEUTRAL_TRANSITIONAL", kalman_dominant_state="transitional"
        )
        if pd.isna(result.get("entry_score", 0.0)):
            return {"status": "FAIL", "detail": "entry_score is NaN — NaN propagation unhandled. "
                    "FIX: call .ffill().dropna() on all series before signal computation."}
        return {"status": "PASS", "detail": f"score={result['entry_score']}, bias={result['entry_bias']}"}
    except Exception as e:
        return {"status": "FAIL", "detail": f"Exception on NaN series: {e}. "
                "FIX: forward-fill all series before access."}


def test_03_entry_engine_empty_vix():
    from src.engines.entry_engine import EntryEngine
    engine = EntryEngine()
    tiny = make_normal_close(10)
    try:
        result = engine.score_entry(
            spx_close_1h=tiny, spx_vol_1h=make_volume_series(10),
            spx_high_1h=tiny, spx_low_1h=tiny,
            vix_1h=pd.Series([], dtype=float),
            dominant_regime="RISK_ON_EXPANSION", kalman_dominant_state="risk_on"
        )
        if result["entry_score"] == 0.5 and result["entry_bias"] == "FLAT":
            return {"status": "PASS", "detail": "Correctly returned 0.5/FLAT for < 26 bars"}
        return {"status": "WARN", "detail": f"Unexpected: {result}"}
    except IndexError as e:
        return {"status": "FAIL", "detail": f"IndexError on empty vix_1h: {e}. "
                "BUG: Early return guard fires BUT VIX fallback on line ~116 still reads vix_1h.iloc[-1]. "
                "FIX: Move vix guard inside score_entry before any iloc access."}
    except Exception as e:
        return {"status": "FAIL", "detail": f"Exception: {e}"}


def test_04_frequency_controller_nan_entropy():
    from src.engines.frequency_controller import FrequencyController
    fc = FrequencyController()
    try:
        r = fc.evaluate(
            shannon_entropy=float("nan"), vix_zscore=0.5,
            dominant_regime="RISK_ON_EXPANSION", brier_score=0.15,
            duration_days=5.0, kalman_dominant_state="risk_on", kalman_is_ambiguous=False
        )
        if pd.isna(r["inputs"].get("shannon_entropy")):
            return {"status": "FAIL", "detail": "NaN entropy stored in output — round(NaN)=NaN propagates. "
                    "FIX: add guard at top of evaluate(): "
                    "if not np.isfinite(shannon_entropy): shannon_entropy = 1.58"}
        return {"status": "PASS", "detail": f"NaN handled, freq={r['recommended_frequency']}"}
    except Exception as e:
        return {"status": "FAIL", "detail": f"NaN entropy crashed: {e}"}


def test_05_frequency_controller_perfect_conditions():
    from src.engines.frequency_controller import FrequencyController
    fc = FrequencyController()
    r = fc.evaluate(
        shannon_entropy=0.5, vix_zscore=-1.0,
        dominant_regime="RISK_ON_EXPANSION", brier_score=0.10,
        duration_days=10.0, kalman_dominant_state="risk_on", kalman_is_ambiguous=False
    )
    # score = +2 (regime) +2 (entropy) +1 (low vix) +1 (good brier) = 6 → should be "1h"
    if r["recommended_frequency"] != "1h":
        return {"status": "FAIL", "detail": f"Perfect conditions returned '{r['recommended_frequency']}' "
                f"(score={r['score']}), expected '1h'. Check scoring logic."}
    return {"status": "PASS", "detail": f"score={r['score']}, freq={r['recommended_frequency']}"}


def test_06_kalman_singular_covariance():
    from src.engines.risk_engine import RiskEngine
    engine = RiskEngine()
    singular_cov = [[0.1, 0.1, 0.1],
                    [0.1, 0.1, 0.1],
                    [0.1, 0.1, 0.1]]
    try:
        ks = engine.run_kalman_filter(
            mcs=50.0, sub_components={},
            hmm_regime_probs={"RISK_ON_EXPANSION": 0.5, "RATE_SHOCK": 0.5},
            prior_cov=singular_cov
        )
        if ks.dominant_state not in ("risk_on", "risk_off", "transitional"):
            return {"status": "FAIL", "detail": f"Invalid dominant_state: {ks.dominant_state}"}
        return {"status": "PASS", "detail": f"Singular covariance handled. dominant_state={ks.dominant_state}"}
    except np.linalg.LinAlgError as e:
        return {"status": "FAIL", "detail": f"LinAlgError on singular covariance: {e}. "
                "FIX: Replace np.linalg.inv(S) with np.linalg.pinv(S), or add P += np.eye(n)*1e-6."}
    except Exception as e:
        return {"status": "FAIL", "detail": f"Unexpected crash: {e}"}


def test_07_risk_off_single_name_gate():
    from src.engines.risk_engine import RiskEngine
    engine = RiskEngine()
    mlp_preds = {k: {"bull_probability": 0.75, "consensus_score": 0.5}
                 for k in ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]}
    mlp_preds["spce"]["bull_probability"] = 0.80

    result = engine.compute_multi_asset_kelly(
        mlp_predictions=mlp_preds, dominant_state="risk_off",
        brier_score=0.18, duration_days=3,
        hmm_regime="CRISIS_DISLOCATION", is_downtrend=True
    )
    bugs = []
    for name in ["NVDA_Kelly", "TSLA_Kelly", "DELL_Kelly", "SPCE_Kelly"]:
        val = result.get(name, 0.0)
        if val > 0.0:
            bugs.append(f"{name}={val}")
    if bugs:
        return {"status": "FAIL",
                "detail": f"Single-name equity positive in risk_off: {', '.join(bugs)}. "
                "BUG: Fix 1 (Universal Equity Regime Gate) was NOT applied to NVDA/TSLA/DELL/SPCE. "
                "FIX: After line 244 (spce_kelly=...), add: "
                "if dominant_state=='risk_off' or is_black_swan: nvda_kelly=tsla_kelly=dell_kelly=spce_kelly=0.0"}
    return {"status": "PASS", "detail": "All single-name equity correctly zeroed in risk_off"}


def test_08_extreme_weakness_amplifier():
    from src.engines.risk_engine import RiskEngine
    engine = RiskEngine()
    mlp_preds = {k: {"bull_probability": 0.53, "consensus_score": 0.4}
                 for k in ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]}
    mlp_preds["spx"]["bull_probability"] = 0.30   # extreme weakness
    mlp_preds["nvda"]["bull_probability"] = 0.65
    mlp_preds["tsla"]["bull_probability"] = 0.63

    result = engine.compute_multi_asset_kelly(
        mlp_predictions=mlp_preds, dominant_state="transitional",
        brier_score=0.18, duration_days=2, hmm_regime="NEUTRAL_TRANSITIONAL"
    )
    nvda_k = result.get("NVDA_Kelly", 0.0)
    tsla_k = result.get("TSLA_Kelly", 0.0)

    if nvda_k > 0.12 or tsla_k > 0.10:
        return {"status": "FAIL",
                "detail": f"NVDA={nvda_k}, TSLA={tsla_k} — Extreme Weakness 1.5x amplifier still active. "
                "BUG: Lines 276-277 still multiply by 1.5. Fix 2 NOT applied. "
                "FIX: Replace nvda_kelly*1.5 / tsla_kelly*1.5 with 0.5x suppression, zero SPCE."}
    return {"status": "PASS", "detail": f"No amplification. NVDA={nvda_k}, TSLA={tsla_k}"}


def test_09_spce_conviction_threshold():
    from src.engines.risk_engine import RiskEngine
    engine = RiskEngine()
    mlp_preds = {k: {"bull_probability": 0.50, "consensus_score": 0.5}
                 for k in ["spx", "btc", "gld", "wti", "nvda", "tsla", "dell", "spce"]}
    mlp_preds["spce"]["bull_probability"] = 0.67  # above 0.65, below recommended 0.72

    result = engine.compute_multi_asset_kelly(
        mlp_predictions=mlp_preds, dominant_state="risk_on",
        brier_score=0.14, duration_days=5, hmm_regime="RISK_ON_EXPANSION"
    )
    spce_k = result.get("SPCE_Kelly", 0.0)
    if spce_k > 0.0:
        return {"status": "FAIL",
                "detail": f"SPCE_Kelly={spce_k} at prob=0.67. Threshold still 0.65 (Fix 3 REVERTED). "
                "FIX: In asset_thresholds dict, set 'spce': 0.72"}
    return {"status": "PASS", "detail": f"SPCE correctly 0 at prob=0.67"}


def test_10_stop_approach_wrong_price():
    from src.engines.market_event_detector import MarketEventDetector
    det = MarketEventDetector()
    prices = {"spx_now": 5200.0, "spx_30m_ago": 5198.0, "vix_now": 18.0, "vix_60m_ago": 17.5}
    # DELL position: peak=$95 (DELL dollars). SPX_now=$5200 will create a massive false drawdown.
    events = det.detect(
        prices=prices, current_entry_score=0.5, current_vix_zscore=0.3,
        portfolio_positions={"DELL": 10.0},
        portfolio_position_details={"DELL": {"peak_price": 95.0}}
    )
    stop_events = [e for e in events if e["type"] == "STOP_APPROACH"]
    if stop_events:
        return {"status": "FAIL",
                "detail": f"FALSE STOP_APPROACH: {stop_events[0]['detail']}. "
                "BUG: Line 123 uses spx_now ($5200) vs DELL peak ($95) → 98% drawdown. "
                "FIX: position_details must store {'current_price': X} per ticker; "
                "detect() must read position_details[ticker].get('current_price', spx_now)."}
    return {"status": "PASS", "detail": "No false stop approach triggered"}


def test_11_detector_stale_regime_stress():
    from src.engines.market_event_detector import MarketEventDetector
    det = MarketEventDetector()
    events = det.detect(
        prices={},  # network failure — empty prices
        current_entry_score=0.5,
        current_vix_zscore=2.5,  # stale snapshot has high vix
        portfolio_positions={}, portfolio_position_details={}
    )
    regime_stress = [e for e in events if e["type"] == "REGIME_STRESS"]
    if regime_stress:
        return {"status": "WARN",
                "detail": "REGIME_STRESS fires from stale vix_zscore even with empty live prices. "
                "If network is down for hours, this will spam pipeline triggers on every 5-min poll. "
                "FIX: Add 'if not prices: return []' at top of detect(), or "
                "track last_successful_fetch_utc and skip regime stress if > 2h stale."}
    return {"status": "PASS", "detail": "Empty prices correctly produces no events"}


def test_12_backtester_date_args():
    import inspect
    try:
        from src.quantitative_backtester import run_backtest
        sig = inspect.signature(run_backtest)
        params = list(sig.parameters.keys())
        if "start_date" not in params or "end_date" not in params:
            return {"status": "FAIL",
                    "detail": "run_backtest() missing start_date/end_date params. Fix 5 not applied."}
        src_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'quantitative_backtester.py')
        with open(src_path, 'r') as f:
            source = f.read()
        if "q1_start >= q1_end" not in source and "start_date > end_date" not in source:
            return {"status": "WARN",
                    "detail": "date args present but no inverted-range guard. "
                    "An end_date before start_date silently produces empty backtest. "
                    "FIX: Add: if q1_start >= q1_end: raise ValueError('start_date must be before end_date')"}
        return {"status": "PASS", "detail": "Date range args and guard both implemented"}
    except ImportError as e:
        return {"status": "FAIL", "detail": f"Import error: {e}"}


tests = [
    ("01 EntryEngine — flat/zero-variance price series",          test_01_entry_engine_flat_price),
    ("02 EntryEngine — NaN-heavy series (data gaps)",             test_02_entry_engine_nan_series),
    ("03 EntryEngine — empty VIX + fewer than 26 bars",           test_03_entry_engine_empty_vix),
    ("04 FrequencyController — NaN entropy input",                test_04_frequency_controller_nan_entropy),
    ("05 FrequencyController — perfect conditions → 1h",          test_05_frequency_controller_perfect_conditions),
    ("06 Kalman Filter — singular covariance matrix",             test_06_kalman_singular_covariance),
    ("07 RiskEngine — single-name gate missing in risk_off",      test_07_risk_off_single_name_gate),
    ("08 RiskEngine — Extreme Weakness 1.5x amplifier (Fix 2)",   test_08_extreme_weakness_amplifier),
    ("09 RiskEngine — SPCE threshold reverted to 0.65 (Fix 3)",   test_09_spce_conviction_threshold),
    ("10 MarketEventDetector — stop uses SPX price for DELL",     test_10_stop_approach_wrong_price),
    ("11 MarketEventDetector — stale snapshot triggers on empty prices", test_11_detector_stale_regime_stress),
    ("12 Backtester — dynamic date range + inversion guard",      test_12_backtester_date_args),
]

print("\n" + "=" * 70)
print("  QuantOS Stress Test Suite")
print("=" * 70 + "\n")

for name, fn in tests:
    run_test(name, fn)

print("\n" + "=" * 70)
passed = sum(1 for _, s, _ in results if s == "PASS")
warned = sum(1 for _, s, _ in results if s == "WARN")
failed = sum(1 for _, s, _ in results if s == "FAIL")
print(f"  Results: {passed} PASS / {warned} WARN / {failed} FAIL  (total {len(results)})")
print("=" * 70 + "\n")

if failed > 0:
    print("FAILED TESTS — exact fixes required:")
    for name, status, detail in results:
        if status == "FAIL":
            print(f"\n  [{name}]")
            print(f"  {detail}")
    sys.exit(1)
