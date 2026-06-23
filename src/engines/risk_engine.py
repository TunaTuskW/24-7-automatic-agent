import numpy as np
import math
from typing import Dict, Any
from src.observability.logger import get_logger
from src.schemas.models import KalmanState

logger = get_logger("risk-engine")

class RiskEngine:
    def run_kalman_filter(self, mcs: float, sub_components: Dict, hmm_regime_probs: Dict, prior_state=None, prior_cov=None) -> KalmanState:
        logger.info("Running Kalman Filter")
        try:
            n = 3
            x = np.array([1/3, 1/3, 1/3]) if prior_state is None else np.array(prior_state)
            P = np.eye(n) * 0.1 if prior_cov is None else np.array(prior_cov).reshape(n, n)
            Q = np.eye(n) * 0.02
            F = np.array([[0.92, 0.04, 0.04], [0.04, 0.92, 0.04], [0.04, 0.04, 0.92]])
            
            hmm_risk_on = hmm_regime_probs.get("RISK_ON_EXPANSION", 0.0) + hmm_regime_probs.get("LIQUIDITY_DRIVEN_RALLY", 0.0)
            
            # Map all known stress and shock states to risk_off
            risk_off_states = ["DEFENSIVE_RISK_OFF", "VOLATILITY_EXPANSION"]
            hmm_risk_off = sum(hmm_regime_probs.get(s, 0.0) for s in risk_off_states)
            
            # Add dynamic checking for indexed states like COMMODITY_SHOCK_4
            for state_name, prob in hmm_regime_probs.items():
                if any(state_name.startswith(base) for base in risk_off_states) and state_name not in risk_off_states:
                    hmm_risk_off += prob
                elif any(state_name.startswith(base) for base in ["RISK_ON", "LIQUIDITY"]) and state_name not in ["RISK_ON_EXPANSION", "LIQUIDITY_DRIVEN_RALLY"]:
                    hmm_risk_on += prob
                    
            hmm_trans = max(0.0, 1.0 - hmm_risk_on - hmm_risk_off)
            
            z = np.array([hmm_risk_on, hmm_risk_off, hmm_trans])
            if z.sum() > 0:
                z /= z.sum()
            else:
                z = np.array([1/3, 1/3, 1/3])
            
            x_pred = F @ x
            P_pred = F @ P @ F.T + Q
            
            H = np.eye(n)
            
            # Dynamic measurement noise to prevent sudden 1-bar regime jumps
            is_sudden_fear = (z[1] > 0.6) and (x[1] < 0.3)
            if is_sudden_fear:
                R = np.eye(n) * 0.25
                logger.info("Sudden fear spike detected. Inflating measurement noise to enforce multi-bar confirmation.")
            else:
                R = np.eye(n) * 0.05
            
            S = H @ P_pred @ H.T + R
            K = P_pred @ H.T @ np.linalg.inv(S)
            
            x_updated = x_pred + K @ (z - H @ x_pred)
            x_updated = np.clip(x_updated, 0.01, 0.99)
            x_updated /= x_updated.sum()
            
            P_updated = (np.eye(n) - K @ H) @ P_pred
            
            max_prob = float(np.max(x_updated))
            is_ambiguous = max_prob < 0.60
            
            states = ["risk_on", "risk_off", "transitional"]
            dominant_idx = int(np.argmax(x_updated))
            
            return KalmanState(
                risk_on=round(float(x_updated[0]), 3),
                risk_off=round(float(x_updated[1]), 3),
                transitional=round(float(x_updated[2]), 3),
                dominant_state=states[dominant_idx],
                dominant_prob=round(float(x_updated[dominant_idx]), 3),
                is_ambiguous=bool(is_ambiguous),
                covariance_matrix=P_updated.tolist(),
                probabilities=x_updated.tolist()
            )
        except Exception as e:
            logger.error(f"Kalman filter failed: {e}")
            return KalmanState()

    def compute_shannon_entropy(self, probs: np.ndarray) -> float:
        try:
            probs = np.clip(probs, 1e-9, 1.0)
            entropy = -np.sum(probs * np.log2(probs))
            return round(float(entropy), 3)
        except Exception:
            return 1.58

    def compute_kelly_sizing(self, max_prob: float, dominant_state: str, brier_score: float, duration_days: float = 0.0, half_life: float = 99.0, sentiment_multiplier: float = 1.0, is_capitulation_override: bool = False, is_momentum_override: bool = False, is_black_swan: bool = False, is_bull_trap: bool = False, hmm_regime: str = "UNKNOWN", current_ihi: float = 0.0, consensus_score: float = 0.0, conviction_threshold: float = 0.60) -> float:
        logger.info(f"Computing Kelly size (prob: {max_prob}, state: {dominant_state}, brier: {brier_score}, consensus: {consensus_score}, threshold: {conviction_threshold})")
        
        if is_bull_trap:
            logger.warning("Bull Trap Override Active: MLP Prob > 0.80 is historically inversely calibrated. Inverting to contrarian bearish.")
            max_prob = 1.0 - max_prob
            
        is_short_bet = False
        effective_prob = max_prob
        if max_prob < 0.5:
            is_short_bet = True
            effective_prob = 1.0 - max_prob
            
        # High Conviction base probability threshold (need at least threshold win rate expectation to play)
        edge = effective_prob - conviction_threshold
        if edge <= 0:
            logger.info(f"No high conviction edge (prob {effective_prob:.3f} <= {conviction_threshold}). Returning 0.0 Kelly allocation.")
            return 0.0
        
        win_rate = effective_prob
        loss_rate = 1.0 - win_rate
        base_fraction = win_rate - (loss_rate / 2.0)
        
        # Baseline Risk Tolerance: High volatility regimes mathematically generate noise.
        # We relax the Brier penalty if the model correctly identified a Risk Off regime.
        # Calibration Penalty (Brier Score scaling) - bypassed by momentum override
        if is_momentum_override:
            calibration_penalty = 1.0
        elif dominant_state == "risk_off":
            if brier_score > 0.45: calibration_penalty = 0.5
            elif brier_score > 0.35: calibration_penalty = 0.9
            else: calibration_penalty = 1.0
        else:
            if brier_score > 0.40: calibration_penalty = 0.5
            elif brier_score > 0.30: calibration_penalty = 0.8
            else: calibration_penalty = 1.0
        
        final_fraction = base_fraction * calibration_penalty
        
        # Apply regime-specific risk aversion penalties
        if is_capitulation_override:
            logger.info("Capitulation Override Active: Bypassing risk-off penalties and applying 0.9x guarded contrarian multiplier.")
            final_fraction *= 0.9 # Guarded contrarian Kelly
        elif is_momentum_override:
            logger.info("Momentum Ignition Active: Bypassing risk-off penalties and applying 1.25x momentum multiplier.")
            final_fraction *= 1.25 # Aggressive trend-following Kelly
                
        # Consensus Risk Modifier (Smooth Linear Scale: 0.7x to 1.2x)
        consensus_multiplier = 0.7 + (consensus_score * 0.5)
        final_fraction *= consensus_multiplier
        logger.info(f"Consensus modifier applied: {consensus_multiplier:.2f}x (score: {consensus_score})")
            
        if duration_days > half_life:
            decay_factor = math.exp(-0.2 * (duration_days - half_life))
            final_fraction *= max(0.2, decay_factor)
            
        final_fraction *= sentiment_multiplier
        
        if is_short_bet:
            final_fraction = -final_fraction
            
        return final_fraction

    def compute_multi_asset_kelly(self, mlp_predictions, dominant_state, brier_score, duration_days=0, is_capitulation_override=False, is_momentum_override=False, is_black_swan=False, is_bull_trap=False, hmm_regime="NEUTRAL_TRANSITIONAL", current_ihi=0.0, is_downtrend=False, max_kelly_cap: float = 0.60, equity_drawdown: float = 0.0, entry_score: float = 1.0):
        if not hmm_regime:
            hmm_regime = "UNKNOWN"
        # Calculate raw kelly for each asset
        raw_allocations = {}
        for asset, preds in mlp_predictions.items():
            prob = preds.get("bull_probability", 0.5)
            consensus_score = preds.get("consensus_score", 0.0)
            
            # P0-6 FIX: Removed Auto-Inversion Module
            # The calibration penalty dynamically scales down exposure for poorly
            # calibrated models, which is safer than blindly inverting bimodal outputs.
            effective_prob = prob

            # Apply bull trap logic ONLY to SPX
            asset_is_bull_trap = False
            if asset == "spx" and is_bull_trap:
                asset_is_bull_trap = True
                
            # Determine Asset-Specific Conviction Threshold
            asset_thresholds = {
                "spx":  0.50,
                "btc":  0.52,
                "gld":  0.52,
                "wti":  0.54,
                "nvda": 0.53,
                "tsla": 0.56,
                "dell": 0.55,
                "spce": 0.72,
            }
            asset_conviction_threshold = asset_thresholds.get(asset, 0.60)
            
            # DYNAMIC CONVICTION SCALING: Boost frequency & accuracy
            # Lower threshold when trading WITH the macro wind, raise when against it.
            is_bull_bet = prob >= 0.5
            if hmm_regime == "LIQUIDITY_DRIVEN_RALLY":
                if is_bull_bet: asset_conviction_threshold -= 0.05
                else: asset_conviction_threshold += 0.05
            elif hmm_regime in ["DEFENSIVE_RISK_OFF", "CRISIS_BEAR_MARKET"]:
                if not is_bull_bet: asset_conviction_threshold -= 0.05
                else: asset_conviction_threshold += 0.05
                
            # Floor/Cap threshold to sane bounds [0.52, 0.75]
            asset_conviction_threshold = max(0.52, min(0.75, asset_conviction_threshold))
            
            raw_kelly = self.compute_kelly_sizing(
                max_prob=effective_prob, 
                dominant_state=dominant_state, 
                brier_score=brier_score, 
                duration_days=duration_days, 
                is_capitulation_override=is_capitulation_override, 
                is_momentum_override=is_momentum_override, 
                is_black_swan=is_black_swan, 
                is_bull_trap=asset_is_bull_trap, 
                hmm_regime=hmm_regime, 
                current_ihi=current_ihi,
                consensus_score=consensus_score,
                conviction_threshold=asset_conviction_threshold
            )
            raw_allocations[asset] = raw_kelly

        # Extract SPX for specific filters
        spx_raw = raw_allocations.get("spx", 0.0)
        spx_kelly = 0.0
        short_kelly = 0.0
        
        # 0.0 means "no edge". A strictly negative value means "active bearish bet".
        # Only the latter should produce a SHORT allocation; no-edge -> cash.
        if spx_raw > 0:
            spx_kelly = round(min(max_kelly_cap, spx_raw), 3)
            if is_downtrend:
                spx_kelly = round(spx_kelly * 0.5, 3)
                logger.warning("SPX is in a macro downtrend. Halving long Kelly allocation.")
        elif spx_raw < -0.05:  # require material bearish edge, not just "no bull edge"
            short_kelly = round(min(max_kelly_cap, abs(spx_raw)), 3)
            logger.info(f"Negative Edge Detected. Shorting enabled with allocation {short_kelly}.")
        # else: spx_raw in [-0.05, 0] -> no actionable edge, leave both at 0 (cash)

        # Black Swan Circuit Breaker overrides SPX
        if is_black_swan:
            logger.error("BLACK SWAN CIRCUIT BREAKER ACTIVE: Liquidating all SPX equity exposure.")
            spx_kelly = 0.0
            
        # Process other assets
        btc_kelly = round(max(0.0, min(1.0, raw_allocations.get("btc", 0.0))), 3)
        gld_kelly = round(max(0.0, min(1.0, raw_allocations.get("gld", 0.0))), 3)
        wti_kelly = round(max(0.0, min(1.0, raw_allocations.get("wti", 0.0))), 3)
        nvda_kelly = round(max(0.0, min(1.0, raw_allocations.get("nvda", 0.0))), 3)
        tsla_kelly = round(max(0.0, min(1.0, raw_allocations.get("tsla", 0.0))), 3)
        dell_kelly = round(max(0.0, min(1.0, raw_allocations.get("dell", 0.0))), 3)
        spce_kelly = round(max(0.0, min(1.0, raw_allocations.get("spce", 0.0))), 3)


        # Capital Rotation Engine (Active Rotation & Diversity)
        spx_prob = mlp_predictions.get("spx", {}).get("bull_probability", 0.5)
        
        # Safe Haven Diversity (Risk-Off / Short environment)
        if dominant_state == "risk_off" or hmm_regime in ("DEFENSIVE_RISK_OFF", "VOLATILITY_EXPANSION"):
            logger.info(f"Risk-Off environment detected. Allocating proportional safe-haven diversity.")
            gld_kelly = max(gld_kelly, 0.20) # 20% safe-haven baseline when defensive
            
        # Extreme Weakness Rotation (Defense / Alpha Rotation)
        if spx_prob < 0.35:
            logger.info("Extreme Weakness: SPX collapsing. Suppressing high-beta names, boosting safe havens.")
            gld_kelly   = min(1.0, round(gld_kelly * 1.5, 3))
            short_kelly = min(1.0, round(short_kelly * 1.2, 3))
            nvda_kelly  = round(nvda_kelly * 0.25, 3)
            tsla_kelly  = round(tsla_kelly * 0.25, 3)
            spce_kelly  = 0.0

        # Universal Equity Regime Gate
        # Kalman risk_off or black swan: zero ALL single-name long equity.
        # SPX is already handled above via is_downtrend. This extends to all names.
        if dominant_state == "risk_off" or is_black_swan:
            nvda_kelly = 0.0
            tsla_kelly = 0.0
            dell_kelly = 0.0
            spce_kelly = 0.0
            if dominant_state == "risk_off":
                btc_kelly = round(btc_kelly * 0.30, 3)
            logger.warning(
                f"Regime Gate: dominant_state={dominant_state}. "
                "All single-name long equity zeroed."
            )

        # HMM Coherence Gate
        # If HMM explicitly names a stress regime, single names are forbidden.
        STRESS_REGIMES = {"DEFENSIVE_RISK_OFF", "VOLATILITY_EXPANSION"}
        if any(hmm_regime.startswith(s) for s in STRESS_REGIMES):
            nvda_kelly = 0.0
            tsla_kelly = 0.0
            dell_kelly = 0.0
            spce_kelly = 0.0
            logger.warning(f"HMM Coherence Gate: {hmm_regime}. Single-name equity zeroed.")

        # Capital Rotation Engine (runs AFTER regime gate so it never re-amplifies zeroed names)
        if spx_kelly > 0.05 and dominant_state != "risk_off" and not is_black_swan:
            if not any(hmm_regime.startswith(s) for s in STRESS_REGIMES):
                nvda_kelly = max(nvda_kelly, round(spx_kelly * 0.35, 3))
                btc_kelly  = max(btc_kelly,  round(spx_kelly * 0.25, 3))
                tsla_kelly = max(tsla_kelly, round(spx_kelly * 0.20, 3))

        # Scale by Entry Score Conviction
        entry_score_multiplier = max(0.3, min(1.0, entry_score))
        spx_kelly = round(spx_kelly * entry_score_multiplier, 3)
        short_kelly = round(short_kelly * entry_score_multiplier, 3)
        btc_kelly = round(btc_kelly * entry_score_multiplier, 3)
        gld_kelly = round(gld_kelly * entry_score_multiplier, 3)
        wti_kelly = round(wti_kelly * entry_score_multiplier, 3)
        nvda_kelly = round(nvda_kelly * entry_score_multiplier, 3)
        tsla_kelly = round(tsla_kelly * entry_score_multiplier, 3)
        dell_kelly = round(dell_kelly * entry_score_multiplier, 3)
        spce_kelly = round(spce_kelly * entry_score_multiplier, 3)
        if entry_score_multiplier < 1.0:
            logger.info(f"Entry Score Multiplier: {entry_score_multiplier:.2f} applied to Kellys.")

        # Global Portfolio Balancer (Normalize exposure)
        total_exposure = spx_kelly + short_kelly + abs(btc_kelly) + abs(gld_kelly) + abs(wti_kelly) + abs(nvda_kelly) + abs(tsla_kelly) + abs(dell_kelly) + abs(spce_kelly)
        if total_exposure > 1.0:
            scale = 1.0 / total_exposure
            spx_kelly = round(spx_kelly * scale, 3)
            short_kelly = round(short_kelly * scale, 3)
            btc_kelly = round(btc_kelly * scale, 3)
            gld_kelly = round(gld_kelly * scale, 3)
            wti_kelly = round(wti_kelly * scale, 3)
            nvda_kelly = round(nvda_kelly * scale, 3)
            tsla_kelly = round(tsla_kelly * scale, 3)
            dell_kelly = round(dell_kelly * scale, 3)
            spce_kelly = round(spce_kelly * scale, 3)
            total_exposure = spx_kelly + short_kelly + abs(btc_kelly) + abs(gld_kelly) + abs(wti_kelly) + abs(nvda_kelly) + abs(tsla_kelly) + abs(dell_kelly) + abs(spce_kelly)

        cash = round(1.0 - (spx_kelly + short_kelly + btc_kelly + gld_kelly + wti_kelly + nvda_kelly + tsla_kelly + dell_kelly + spce_kelly), 3)
            
        return {
            "SPX_Kelly": spx_kelly,
            "Short_Kelly": short_kelly,
            "BTC_Kelly": btc_kelly,
            "GLD_Kelly": gld_kelly,
            "WTI_Kelly": wti_kelly,
            "NVDA_Kelly": nvda_kelly,
            "TSLA_Kelly": tsla_kelly,
            "DELL_Kelly": dell_kelly,
            "SPCE_Kelly": spce_kelly,
            "Cash": cash
        }
