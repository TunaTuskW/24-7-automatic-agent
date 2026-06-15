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
            risk_off_states = ["STAGFLATION_STRESS", "RATE_SHOCK", "DEFLATION_FEAR", "CRISIS_DISLOCATION", "COMMODITY_SHOCK", "VOLATILITY_EXPANSION"]
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
        if is_momentum_override:
            calibration_penalty = 1.0
            logger.info("Momentum Ignition Active: Bypassing Brier Score penalties.")
        elif dominant_state == "risk_off":
            if brier_score > 0.35: calibration_penalty = 0.5
            elif brier_score > 0.20: calibration_penalty = 0.9
            else: calibration_penalty = 1.0
        else:
            if brier_score > 0.25: calibration_penalty = 0.5
            elif brier_score > 0.15: calibration_penalty = 0.8
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

    def compute_multi_asset_kelly(self, mlp_predictions, dominant_state, brier_score, duration_days=0, is_capitulation_override=False, is_momentum_override=False, is_black_swan=False, is_bull_trap=False, hmm_regime="NEUTRAL_TRANSITIONAL", current_ihi=0.0, is_downtrend=False, max_kelly_cap: float = 0.40, equity_drawdown: float = 0.0):
        # Calculate raw kelly for each asset
        raw_allocations = {}
        for asset, preds in mlp_predictions.items():
            prob = preds.get("bull_probability", 0.5)
            consensus_score = preds.get("consensus_score", 0.0)
            
            # AUTO-INVERSION MODULE
            if brier_score > 0.60:
                # The model is negatively calibrated (overfitted mean-reversion). Flip the probability.
                inverted_prob = round(1.0 - prob, 3)
                logger.warning(f"[AUTO-INVERSION TRIGGERED] {asset.upper()} model is negatively correlated (Brier: {brier_score:.3f}). Inverting probability: {prob} -> {inverted_prob}")
                prob = inverted_prob

            # Apply bull trap logic ONLY to SPX
            asset_is_bull_trap = False
            if asset == "spx" and is_bull_trap:
                asset_is_bull_trap = True
                
            # Equity Curve Smoothing: Reduce risk if we are in a drawdown
            if equity_drawdown > 0.05:
                logger.warning(f"Equity Curve Smoothing Active: Current drawdown is {equity_drawdown:.2%}. Reducing max_kelly_cap by 50%.")
                max_kelly_cap = max(0.10, max_kelly_cap * 0.5)
            
            # Determine Asset-Specific Conviction Threshold
            asset_thresholds = {
                "spx":  0.58,   # Core index, slightly lower threshold
                "btc":  0.63,   # High volatility, tighter
                "gld":  0.55,   # Safe haven, lower threshold to hedge
                "wti":  0.60,
                "nvda": 0.63,   # High vol tech, tightened from 0.60
                "tsla": 0.65,   # High vol, tightened from 0.62
                "dell": 0.63,   # Tightened from 0.60
                "spce": 0.72,   # Near-zero liquidity — requires extraordinary conviction
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
                max_prob=prob, 
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
        
        # Macro Trend Override: Block Longs in technical downtrends
        if is_downtrend and spx_raw > 0:
            logger.info("Macro Trend Override active (SPX below 20 EMA). Forcing SPX Long Kelly to 0.0.")
            spx_raw = 0.0
            

        spx_kelly = 0.0
        short_kelly = 0.0
        
        if spx_raw > 0:
            spx_kelly = round(min(max_kelly_cap, spx_raw), 3)
            # Retail Noise Filter as an active risk multiplier
            if dominant_state != "risk_off" and current_ihi < 0.0:
                logger.info(f"Retail Noise Filter active: dominant_state={dominant_state}, current_ihi={current_ihi}. Slashed SPX Kelly fraction by 50%.")
                spx_kelly = round(spx_kelly * 0.5, 3)
        else:
            short_kelly = round(min(1.0, abs(spx_raw)), 3)
            if dominant_state == "transitional":
                short_kelly = round(short_kelly * 0.6, 3)
            logger.info(f"Negative Edge Detected. Activating Short Kelly: {short_kelly}")

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

        # Universal Equity Regime Gate
        # When Kalman state is risk_off, suppress all single-name long equity exposure.
        # SPX is already handled by is_downtrend above. This extends that gate to all names.
        if dominant_state == "risk_off" or is_black_swan:
            logger.warning(
                f"Regime Gate: dominant_state={dominant_state}. "
                "Suppressing all single-name long equity (NVDA, TSLA, DELL, SPCE)."
            )
            nvda_kelly = 0.0
            tsla_kelly = 0.0
            dell_kelly = 0.0
            spce_kelly = 0.0
            # BTC partial suppression: correlated with equity in hard selloffs
            if dominant_state == "risk_off":
                btc_kelly = round(btc_kelly * 0.30, 3)
                
        # HMM Regime Coherence Gate
        # When HMM explicitly identifies a stress or shock state, zero all single-name equity
        # regardless of Kalman state. The Kalman filter may lag the HMM on sudden regime shifts.
        STRESS_REGIMES = {
            "STAGFLATION_STRESS", "RATE_SHOCK", "DEFLATION_FEAR",
            "CRISIS_DISLOCATION", "VOLATILITY_EXPANSION", "COMMODITY_SHOCK", "RISK_OFF_STRESS"
        }
        if any(hmm_regime.startswith(s) for s in STRESS_REGIMES):
            logger.warning(
                f"HMM Coherence Gate: {hmm_regime} is a stress regime. "
                "Zeroing all single-name long equity."
            )
            nvda_kelly = 0.0
            tsla_kelly = 0.0
            dell_kelly = 0.0
            spce_kelly = 0.0
        # Capital Rotation Engine (Active Rotation & Diversity)
        spx_prob = mlp_predictions.get("spx", {}).get("bull_probability", 0.5)
        
        # High Beta Diversity (Risk-On environment)
        if spx_kelly > 0.05:
            logger.info(f"Risk-On environment detected. Allocating proportional high-beta diversity.")
            nvda_kelly = max(nvda_kelly, round(spx_kelly * 0.35, 3)) # 35% of SPX exposure
            btc_kelly = max(btc_kelly, round(spx_kelly * 0.25, 3))  # 25% of SPX exposure
            tsla_kelly = max(tsla_kelly, round(spx_kelly * 0.20, 3))
            
        # Safe Haven Diversity (Risk-Off / Short environment)
        if short_kelly > 0.05:
            logger.info(f"Risk-Off environment detected. Allocating proportional safe-haven diversity.")
            gld_kelly = max(gld_kelly, round(short_kelly * 0.40, 3)) # 40% of short exposure
            
        # Extreme Weakness: SPX collapsing means high-beta single names fall harder.
        # Suppress rather than amplify. Redirect defensive capital to safe havens only.
        if spx_prob < 0.40:
            logger.info(
                f"Extreme Weakness detected (spx_prob={spx_prob:.3f}). "
                "Suppressing single-name amplification."
            )
            nvda_kelly = round(nvda_kelly * 0.50, 3)
            tsla_kelly = round(tsla_kelly * 0.50, 3)
            spce_kelly = 0.0  # Never hold SPCE in extreme SPX weakness

        # Global Portfolio Balancer (Normalize exposure)
        total_exposure = spx_kelly + short_kelly + btc_kelly + gld_kelly + wti_kelly + nvda_kelly + tsla_kelly + dell_kelly + spce_kelly
        if total_exposure > 1.2:
            scale = 1.2 / total_exposure
            spx_kelly = round(spx_kelly * scale, 3)
            short_kelly = round(short_kelly * scale, 3)
            btc_kelly = round(btc_kelly * scale, 3)
            gld_kelly = round(gld_kelly * scale, 3)
            wti_kelly = round(wti_kelly * scale, 3)
            nvda_kelly = round(nvda_kelly * scale, 3)
            tsla_kelly = round(tsla_kelly * scale, 3)
            dell_kelly = round(dell_kelly * scale, 3)
            spce_kelly = round(spce_kelly * scale, 3)
            total_exposure = spx_kelly + short_kelly + btc_kelly + gld_kelly + wti_kelly + nvda_kelly + tsla_kelly + dell_kelly + spce_kelly

        cash = round(max(0.0, 1.0 - total_exposure), 3)
            
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
