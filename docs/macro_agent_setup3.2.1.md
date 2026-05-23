# Macro Briefing Agent - v3.2.1 Patch Notes

## Algorithmic Refinement Update
- **Statistical Noise Filtering:** The deterministic synthesis engine now explicitly filters out statistical noise. If the primary Kalman classifier drops below `60.0%` probability (indicating a statistical coin flip), the system will no longer attempt to force a directional lean.
- **"No Predict" Governance:** When ambiguous noise is detected, the algorithm overrides the `Directional Lean` and `Positioning` blocks with explicit "NO PREDICT / No Comment" tags, clearly communicating to the user that the current market action is indistinguishable from noise and they should stand aside.
