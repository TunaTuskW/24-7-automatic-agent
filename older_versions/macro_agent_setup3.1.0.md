# Macro Briefing Agent - v3.1.0 Patch Notes

## Core Identity Update
- **Stripped Theatrical Formatting:** Removed all dramatic, marketing-style adjectives (e.g., "elite institutional", "TruChain-signed", "Double-engine") from the prompt instructions and deterministic fallbacks.
- **Model Agnosticism:** Stripped internal model naming structures (e.g., "Bayesian HMM", "Deep MLP Classifier"). The report now presents the math purely as quantitative state tracking.

## Mathematical Upgrades (Carried Over & Refined)
- **Total Variation Distance (TVD):** Officially replacing KL Divergence for measuring the distance between the two primary mathematical engines.
- **Brier Score Bounds:** Corrected the scoring vector to accurately average squared errors, and wired a hard-cap into the LLM prompt. If the Brier Score exceeds `0.25` (worse than random guessing), the LLM must instantly downgrade the `Confidence Level` to `LOW`.
- **Probability Clipping:** Enforced `np.clip(0.01, 0.99)` across all neural state probability arrays to eliminate absolute-zero logic traps during downstream filtering.

## Report Generation Logic
- **Bypass Disabled:** The strict 3-line terminal bypass has been removed in favor of generating the full qualitative report regardless of market ambiguity, using the Brier/TVD math constraints to logically express that ambiguity instead.
