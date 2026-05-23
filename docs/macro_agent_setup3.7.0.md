# Macro Briefing Agent - v3.7.0 Patch Notes

## Brutalist Terminal UI & Pipeline Hardening
The presentation layer has been entirely rewritten to drop standard Markdown headers in favor of an ultra-minimal, Brutalist Terminal text-block layout. This prevents rendering inconsistencies across Discord, Telegram, and mobile interfaces. Additionally, critical data drop bugs affecting the `Volume Heat` and `Market Extremes` diagnostic engines have been patched.

### Features & Fixes Implemented:
- **Volume Heat Restored (Pipeline Fix):** A silent failure in `fetch_market_data.py` where Volume Heat and Market Extremes were returning `UNKNOWN` due to a truncated 15-day fetch window has been patched. The engine now correctly pulls a 30-day window, satisfying the 20-day rolling requirements for institutional volume footprinting.
- **Index Key Remapping:** Hardcoded "SPX" and "VIX" string references in the extremes diagnostic block have been correctly remapped to their Yahoo Finance raw index keys (`^GSPC` and `^VIX`), restoring the data flow.
- **Brutalist Presentation Layer:** Standard markdown headers have been replaced with a monospace ` ```text ` block layout. The new `[ QUANTITATIVE MATRIX ]` and `[ SYSTEM HEALTH ]` headers create a cleaner, data-dense reading experience tailored for instant mobile parsing.
