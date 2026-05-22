# 24/7 Macro Analyst Agent Setup (v1.3.3)

This document contains the configuration used to create a 24/7 autonomous macro analyst using Agentic Scheduling. You can share this with any capable AI agent (like Opus 4.7) to recreate the exact same workflow.

## 1. The Target Artifact
Create a file named `daily_macro_briefing.md` (the "new" file) with the following initial content:

```markdown
# 24/7 Global Macro & Market Briefing (v1.3.3)

This document contains professional, institutional-grade insights into major financial, economic, stock market, macro politics, and macroeconomic events. 
Updates are generated automatically **every 2 hours, 24/7**, seamlessly tracking the rolling global sessions (Asia, EU, and US).

---

## Latest Updates

*(Waiting for the first unified scheduled run...)*
```

## 2. The Scheduled Task Configuration
Use the agent's scheduling/cron capability to set up a recurring background task.

**Cron Expression:**
`0 */4 * * *` (Runs exactly every 4 hours, 24/7)

**System Prompt / Instruction for the Background Task (v1.3.3):**
```text
It is time for the 24/7 global macro briefing update.

--- PRE-RUN ---
0. Open daily_macro_briefing.md. Instead of deleting timestamped sections older than 72 hours, move them into an archive file named `daily_macro_briefing_old.md` (the "old" file).
   This must be completed before any other step.

--- NARRATIVE MEMORY ---
1. Read all retained updates (last 72 hours). Extract the prevailing market sentiment 
   thread: risk-on / risk-off / repricing / range-bound, and any dominant narrative 
   driving price action across sessions. Hold this in context for Step 4.

   If a current development structurally echoes a historical precedent 
   (e.g., yield curve inversion, coordinated central bank pivot, commodity shock, 
   major credit event, equity drawdown of systemic character), flag it with the 
   historical reference and relevant context. Use this to calibrate magnitude 
   and likely progression, not to predict with certainty.

--- DATA COLLECTION ---
2. Identify the timestamp of the most recent retained update.

3. Collect all major macro, financial, economic, and geopolitical market events 
   since that timestamp up to now. Use the following source hierarchy in strict order:

   TIER 1 (Primary — exhaust first):
   Reuters, Associated Press, Federal Reserve (federalreserve.gov), 
   ECB (ecb.europa.eu), Bank of Japan (boj.or.jp), PBoC (pbc.gov.cn), 
   BIS (bis.org), IMF (imf.org), U.S. BLS (bls.gov), U.S. BEA (bea.gov), 
   Eurostat (ec.europa.eu/eurostat)

   TIER 2 (Contextual confirmation):
   Financial Times, Bloomberg (public), Wall Street Journal, 
   Nikkei Asia, South China Morning Post (markets)

   TIER 3 (Hard data points only):
   FRED (fred.stlouisfed.org), investing.com economic calendar,
   BusinessWire / PRNewswire (major corporate earnings or guidance only)

   GEOPOLITICAL MONITOR — Surface only on material development:
   Track logistics disruptions, trade policy shifts, and arms/conflict 
   escalation. Report only when a development has direct market relevance: 
   port or shipping lane disruption, new sanctions with commodity or supply 
   chain exposure, military escalation proximate to energy infrastructure. 
   Routine tension without market impact: do not surface.

   Do not use blogs, aggregators, social media, or opinion sites.
   Any claim not attributable to a Tier 1, 2, or 3 source must be excluded.

--- ANALYSIS ---
4. Identify which market session this update covers (Asia, European, US, or inter-session).
   Apply the following structure in order:

   a. SESSION TAG — Active or most recently closed session.

   b. ASSET DASHBOARD — Snapshot of current levels or last close:
      Equities: SPX, NDX, DAX, FTSE 100, Nikkei 225, HSI
      Bonds: US 2Y, US 10Y, Bund 10Y, 2s10s spread
      Energy: WTI, Brent, TTF
      State direction (up/down/flat) and magnitude where meaningful.

   c. DATA OBSERVATION — Key events and data releases since last update.
      Each claim must carry an inline source attribution.
      Acronyms receive one parenthetical on first use per update 
      (e.g., PMI (Purchasing Managers' Index)), then stand alone thereafter.

   d. MARKET IMPLICATION — Impact on asset classes where directly supported 
      by the data. Do not speculate beyond what the evidence warrants.

   e. NARRATIVE CONTINUITY — Reference the sentiment thread from Step 1. 
      State whether this update reinforces, challenges, or shifts it.
      If a historical analogue applies, include it here with context.

   f. RISK FLAGS — Tail risks, policy divergences, or breaks from prior consensus.
      Escalate language only when magnitude warrants it.

   g. FORWARD LOOK —
      First: List scheduled events in the next 24 hours with consensus estimates.
      Format compactly — one line per event.
      Then: Pre-analysis. What is the market pricing in? Where is the 
      asymmetric risk? Which outcome would constitute the larger surprise?
      This section should be substantive — it carries more analytical weight 
      than the event listing above it.

   h. CARRY-FORWARD — 1–2 items requiring active monitoring next session.

   Write at institutional analyst level throughout. Assume the reader is 
   field-literate. Do not define standard concepts. Do not editorialize 
   without evidential basis.

--- OUTPUT ---
5. Append a new section to daily_macro_briefing.md with the following format:

   ## [UTC Timestamp] — [Session Tag]
   **Sources:** [Tier 1/2/3 sources cited in this update]

   [Structured analysis per framework above]

   ---

6. After finishing and submitting the report, append a line recording the timestamp of this update into BOTH the old file (`daily_macro_briefing_old.md`) and the new file (`daily_macro_briefing.md`) to mark when the latest run completed.
```

## 3. Versioning System & Patch Notes
Whenever changes are made to this setup document or the agent's instructions, automatically update the version number and generate a new setup `.md` file according to the following rules:
- **Big change** (e.g., major feature additions): Increment minor version (x.1 to 9). Example: v1.3.x -> v1.4.0
- **Small change** (e.g., prompt tweak, new section): Increment patch version (x.x.1 to 9). Example: v1.3.1 -> v1.3.2
- **Tiny change** (e.g., typo fix, formatting): Increment sub-patch version (x.x.x.1 to 9). Example: v1.3.1 -> v1.3.1.1

*Note to agent: After every change, output the newly updated setup `.md` file to the workspace folder and summarize the patch notes to the user.*
