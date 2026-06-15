class FrequencyController:
    """
    Determines optimal execution frequency based on regime confidence,
    volatility state, and model calibration quality.
    
    Outputs one of: "1h", "4h", "1d"
    """

    # Thresholds
    ENTROPY_HIGH  = 1.20   # bits — above this = regime is ambiguous
    ENTROPY_MED   = 0.90   # bits — above this = some uncertainty
    VIX_Z_HIGH    = 1.50   # z-score above this = elevated volatility regime
    VIX_Z_MED    = 0.75
    BRIER_POOR    = 0.25   # above this = model is degraded, no point trading fast
    DURATION_MIN  = 2      # regime must have lasted at least 2 days before trusting it

    REGIME_FREQ_CAPABLE = {
        "RISK_ON_EXPANSION",
        "LIQUIDITY_DRIVEN_RALLY",
    }

    def evaluate(
        self,
        shannon_entropy: float,
        vix_zscore: float,
        dominant_regime: str,
        brier_score: float,
        duration_days: float,
        kalman_dominant_state: str,
        kalman_is_ambiguous: bool
    ) -> dict:
        """
        Returns:
          recommended_frequency: "1h" | "4h" | "1d"
          reason: str
          metrics: dict for logging
        """
        reason_parts = []
        score = 0  # higher = more confident = higher frequency allowed

        # Factor 1: Regime must be in a high-frequency capable state
        if dominant_regime in self.REGIME_FREQ_CAPABLE:
            score += 2
        elif kalman_dominant_state == "transitional" or kalman_is_ambiguous:
            score -= 2
            reason_parts.append("regime ambiguous or transitional")

        # Factor 2: Shannon entropy (regime probability distribution spread)
        if shannon_entropy < self.ENTROPY_MED:
            score += 2
        elif shannon_entropy < self.ENTROPY_HIGH:
            score += 1
        else:
            score -= 1
            reason_parts.append(f"high regime entropy ({shannon_entropy:.2f})")

        # Factor 3: VIX z-score (volatility regime)
        if vix_zscore < self.VIX_Z_MED:
            score += 1
        elif vix_zscore > self.VIX_Z_HIGH:
            score -= 2
            reason_parts.append(f"elevated VIX z-score ({vix_zscore:.2f})")

        # Factor 4: Model calibration quality
        if brier_score < 0.15:
            score += 1
        elif brier_score > self.BRIER_POOR:
            score -= 1
            reason_parts.append(f"degraded model Brier score ({brier_score:.3f})")

        # Factor 5: Regime must have persisted (avoid false starts)
        if duration_days < self.DURATION_MIN:
            score -= 1
            reason_parts.append(f"regime too new ({duration_days:.1f} days)")

        # Map score to frequency
        if score >= 4:
            freq = "1h"
            reason = "High confidence regime with confirmed trend and clean volatility."
        elif score >= 1:
            freq = "4h"
            reason = "Moderate confidence. Standard 4H cadence."
        else:
            freq = "1d"
            reason = f"Low confidence — reducing to daily cadence. Factors: {'; '.join(reason_parts) or 'general uncertainty'}."

        return {
            "recommended_frequency": freq,
            "score": score,
            "reason": reason,
            "inputs": {
                "shannon_entropy": round(shannon_entropy, 3),
                "vix_zscore": round(vix_zscore, 3),
                "dominant_regime": dominant_regime,
                "brier_score": round(brier_score, 4),
                "duration_days": round(duration_days, 2),
                "kalman_is_ambiguous": kalman_is_ambiguous
            }
        }
