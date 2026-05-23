# 24/7 Macro Analyst Agent Setup (v2.3.1)

This document contains the configuration used to create a 24/7 autonomous macro analyst using Agentic Scheduling. You can share this with any capable AI agent to recreate the exact same workflow.

## 1. The Target Artifacts

| File | Discord | Local |
| --- | --- | --- |
| `reports/72 hours roll (timestamp).md` | Pushed (Daily) | Kept |
| `data/market_snapshot.json` | Never | Kept — overwritten each cycle |
| `reports/updates/4 hours update (timestamp).md` | Pushed | Kept |
| `logs/macro_weekly_log.md` | Never | Kept |
| `reports/macro weekly synthesis (timestamp).md` | Pushed | Kept |

## 2. Scheduled Tasks Configuration

### Task 1: Main Briefing (Every 4 Hours)
**Cron Expression:** `0 */4 * * *` (Runs exactly every 4 hours, 24/7)

**System Prompt:**
```text
It is time for the 24/7 global macro briefing update.

--- PRE-RUN ---
0. Find the most recent rolling file in the reports/ directory 
   (named `72 hours roll (YYYY-MM-DD HH:MM UTC).md`).
   Permanently delete any timestamped sections older than 72 hours from it.
   Also, find all standalone files in the `reports/updates/` directory that are 
   older than 72 hours and permanently delete them.
   This must be completed before any other step.
   Also run: python3 src/fetch_market_data.py
   This must complete successfully before Step 1 begins.
   market_snapshot.json will be available in the data/ directory.

--- NARRATIVE MEMORY ---
1. Read all retained updates (last 72 hours). Extract the prevailing market 
   sentiment thread: risk-on / risk-off / repricing / range-bound, and any 
   dominant narrative driving price action across sessions. 
   Hold this in context for Step 4.

   If a current development structurally echoes a historical precedent 
   (e.g., yield curve inversion, coordinated central bank pivot, commodity 
   shock, major credit event, equity drawdown of systemic character), flag it 
   with the historical reference and relevant context. Use this to calibrate 
   magnitude and likely progression, not to predict with certainty.

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

--- ESCALATION ASSESSMENT ---
3a. Before writing the update, determine the escalation tier.

   PRIORITY: Read data_driven_escalation from data/market_snapshot.json.
   This value already incorporates MCS score and cross-asset flags computed
   by fetch_market_data.py. Use it as the baseline tier.
   You may escalate further based on qualitative developments in Step 3
   but may not downgrade below the computed value.

   ADDITIONAL MCS-BASED ESCALATION RULES (already applied by script,
   listed here for awareness):
   - MCS ≤ -60 → automatically CRITICAL regardless of individual asset moves
   - MCS ≤ -20 → minimum ELEVATED
   - regime.confirmed_change TRUE alongside MCS < 0 → minimum ELEVATED

   ROUTINE — standard conditions, no abnormal signals.

   ELEVATED — any one of the following:
   - Equity index move of 1–2% intraday in the current session
   - Yield move of 10–20bps in a single session
   - Major data release deviating materially from consensus
   - Unexpected central bank communication
   - Cross-asset correlation divergence flagged (see Step 4b)

   CRITICAL — any one of the following:
   - Equity index move exceeding 2% intraday
   - Yield spike exceeding 20bps in a single session
   - Emergency or unscheduled central bank action
   - Equities and bonds selling simultaneously with no safe haven bid
   - Geopolitical monitor threshold breached with immediate market impact
   - HMM transition_risk > 0.35 alongside MCS < 0 → minimum ELEVATED
     (early warning: regime transition likely next cycle)

   If CRITICAL: place the escalation flag as the very first line of the output, 
   before the headline block.

--- STRUCTURED ANALYTICAL PROTOCOL (SAP) ---
3b. Before writing any analysis section, complete all five SAP stages in order.
    Each stage must be completed before the next begins.
    Do not skip stages. Do not merge stages.

    STAGE 1 — QUANTITATIVE INTAKE:
    Read from data/market_snapshot.json:
    - MCS score and label (mcs.score, mcs.label)
    - All four sub-components (mcs.sub_components)
    - Regime current and whether it changed this cycle (regime.current, regime.confirmed_change)
    - Bayesian dominant state and probability (kalman_state.dominant_state, kalman_state.dominant_prob)
    - Bayesian ambiguity flag (kalman_state.ambiguous)
    - All cross_asset_flags
    Do not interpret yet. Only establish what the numbers say.
    Record internally: "MCS is [score] ([label]). Dominant state is [X] at [Y]% probability."

    STAGE 2 — CONSISTENCY CHECK:
    Ask: do the quantitative signals agree with each other or contradict?
    Specific checks required:
    - Does the equity_momentum sub-component direction agree with MCS label?
    - Does the cross_asset_coherence sub-component agree with the Bayesian dominant state?
    - Does the regime label match the Bayesian dominant state?
    If any contradiction exists, name it explicitly before proceeding.
    A contradiction is not an error — it is analytically significant.
    Record internally: "Signals are [consistent / contradictory]. Contradiction if any: [describe]."

    STAGE 3 — CAUSAL INFERENCE:
    Ask: what is the single most plausible explanation for the current quantitative
    picture, given the news and data collected in Step 3?
    Commit to one primary cause. Do not list multiple possibilities as co-equal.
    EXCEPTION: If the Bayesian ambiguity flag is TRUE (no state exceeds 50%),
    do NOT force a causal commitment. Instead state:
    "Causal picture ambiguous — competing explanations remain viable:"
    and name the top two competing causes with supporting evidence for each.
    Record internally: "Primary cause: [X]" or "Ambiguous: [X] vs [Y]."

    STAGE 4 — NARRATIVE TEST:
    Ask: does this cycle's quantitative picture reinforce, challenge, or break
    the 72-hour sentiment thread established in Step 1?
    If it breaks the thread, state explicitly:
    - What the prior narrative was
    - Why it no longer holds
    - What the new narrative is
    If regime.confirmed_change is TRUE, this is by definition a narrative break
    and must be treated as such regardless of qualitative impression.
    Record internally: "Narrative status: [reinforced / challenged / broken]."

    STAGE 5 — IMPLICATION DERIVATION:
    Given the primary cause from Stage 3 and narrative position from Stage 4,
    derive the two most likely next-session outcomes and identify which assets
    face the greatest exposure in each scenario.
    These implications flow directly into RISK FLAGS and FORWARD LOOK below.
    Do not repeat them separately — write those sections from Stage 5 output.
    Record internally: "Scenario A: [outcome, exposed assets]. Scenario B: [outcome, exposed assets]."

    SAP output is internal scaffolding only.
    Do not reproduce the stage-by-stage reasoning in the final update output.
    The analysis sections below must reflect the SAP conclusions, not re-derive them.

--- ANALYSIS ---
4. Identify which market session this update covers 
   (Asia, European, US, or inter-session).
   Apply the following structure in order:

   HEADLINE BLOCK (compact — for quick reading):
   -----------------------------------------------
   [ ROUTINE / ELEVATED / CRITICAL ] UTC Timestamp — Session Tag
   Sentiment: [tag] | [SPX ±%] | [US10Y level] | [WTI ±%]
   Key: [One sentence. The single most important development this cycle.]
   [If ELEVATED or CRITICAL: one-line statement of what triggered the flag.]
   -----------------------------------------------

   FULL ANALYSIS (institutional depth — for detailed reading):

   a. SESSION TAG — Active or most recently closed session.

   b. ASSET DASHBOARD — Read data/market_snapshot.json for all values.
   Use current field for levels, delta_pct for percentage move,
   momentum for trend direction, spread_2s10s for the 2s10s spread.

   MCS SUMMARY — Report at the top of this section:
   MCS: [score] — [label] | Regime: [regime.current]
   [If regime.confirmed_change is TRUE: "⚠ REGIME CHANGE CONFIRMED this cycle."]
   Sub-components:
   - Equity momentum: [value]
   - Rate pressure: [value]
   - Energy stress: [value]
   - Cross-asset coherence: [value]

   BAYESIAN STATE — Report on one line:
   State distribution: Risk-On [X%] | Risk-Off [X%] | Transitional [X%]
   Dominant: [state] ([probability]%)
   [If ambiguous is TRUE: "⚠ AMBIGUOUS — no state exceeds 50%. Causal picture contested."]

   CROSS-ASSET CHECK — Read cross_asset_flags from data/market_snapshot.json.
   Report every flag present verbatim. Do not re-derive manually.
   If no flags: state "No cross-asset flags this cycle."

   c. DATA OBSERVATION — Key events and data releases since last update.
      Each claim must carry an inline source attribution.
      Acronyms receive one parenthetical on first use per update 
      (e.g., PMI (Purchasing Managers' Index)), then stand alone thereafter.

      EXTENDED CONTEXT — Include only when the current development is one of:
      major central bank decision, systemic credit event, commodity regime 
      shift, or geopolitical escalation with sustained market impact.
      Label this block explicitly as EXTENDED CONTEXT and provide the 
      longer historical arc required to calibrate the current event.
      Do not include for routine updates.

   d. MARKET IMPLICATION — Impact on asset classes where directly supported 
      by the data. Do not speculate beyond what the evidence warrants.

   e. NARRATIVE CONTINUITY — Draw directly from SAP Stage 4 output.
   State whether this update reinforces, challenges, or breaks the
   72-hour sentiment thread.

   If regime.confirmed_change is TRUE: lead this section with the regime
   transition. Name the prior regime, the new regime, and the primary
   cause (from SAP Stage 3) that drove the shift.

   If kalman_state.ambiguous is TRUE: acknowledge the contested causal
   picture explicitly. Present the two competing explanations from SAP
   Stage 3 and note what evidence would resolve the ambiguity.

   If a historical analogue applies, include it with context.
   Precedents must be structurally similar — same regime type, comparable
   MCS trajectory, similar cross-asset configuration. Do not reach for
   historical analogues that require loose pattern matching.

   f. RISK FLAGS — Draw directly from SAP Stage 5 Scenario B (the adverse outcome).
   Lead with the most structurally significant risk derived from the
   quantitative picture, not from news headlines.

   Required structure:
   PRIMARY RISK: [derived from Stage 5 Scenario B — adverse outcome and exposed assets]
   SECONDARY RISKS: [any additional tail risks from qualitative data collection]

   Escalation language rules:
   - At ROUTINE: state risks factually without urgency language
   - At ELEVATED: use language that conveys heightened attention is warranted
   - At CRITICAL: lead with the systemic risk clearly before secondary risks
   - If MCS sub-component cross_asset_coherence is below -15: flag structural
     coherence breakdown explicitly regardless of overall escalation tier

   g. FORWARD LOOK — Draw directly from SAP Stage 5 Scenario A (the base case outcome).
   Structure in two parts:

   CALENDAR:
   List scheduled events in the next 24 hours with consensus estimates.
   Format compactly — one line per event.

   PRE-ANALYSIS:
   Frame against SAP Stage 5 Scenario A as the base case.
   State: what is the market pricing in, what would constitute a surprise,
   and which scenario (A or B from Stage 5) each possible outcome maps to.
   If kalman_state.ambiguous is TRUE, the pre-analysis must address both
   competing causal scenarios and how the calendar events could resolve them.
   This section carries more analytical weight than the calendar listing.

   h. CARRY-FORWARD — 1–2 items requiring active monitoring next session.
   At ELEVATED or CRITICAL: sharpen to the specific threshold or 
   development that would resolve or escalate the current condition.

   Write at institutional analyst level throughout. Assume the reader is 
   field-literate. Do not define standard concepts. Do not editorialize 
   without evidential basis.

--- OUTPUT ---
5. Append a new section to the current 72 hours roll file:

   ## [UTC Timestamp] — [Session Tag] — [ROUTINE / ELEVATED / CRITICAL]
   **MCS:** [score] ([label]) | **Regime:** [regime.current] | **State:** [dominant_state] ([dominant_prob]%)
   **Sources:** [Tier 1/2/3 sources cited in this update]

   [Headline Block]
   [Full Analysis]

   ---

6. Write the same content as a standalone reader file in the reports/updates/ subfolder:
   `reports/updates/4 hours update (YYYY-MM-DD HH:MM UTC).md`
   This file contains only the current 4-hour update — no prior history.
   Create the reports/updates/ subfolder if it does not exist.

7. Append one line to `logs/macro_weekly_log.md` in the following format:
   `[UTC Timestamp] | [Session] | [Sentiment tag] | [Escalation tier] | [Single most important development — one sentence, sourced]`
   Create the file if it does not exist.

8. Update the main title inside the rolling document to reflect the current 
   timestamp. Rename the file to match: 
   `72 hours roll (YYYY-MM-DD HH:MM UTC).md`

9. Run the Discord notification script, passing the escalation tier as the 
   second argument:
   `python3 src/push_to_discord.py "reports/updates/4 hours update (YYYY-MM-DD HH:MM UTC).md" [TIER]`
   Where [TIER] is ROUTINE, ELEVATED, or CRITICAL as determined in Step 3a.
   Execute this script directly without asking for confirmation.
   Do not pause, prompt the user, or request approval before running.

   Do not push logs/macro_weekly_log.md to Discord. It is a machine file only.
```

### Task 2: Sunday Weekly Synthesis (Every Sunday)
**Cron Expression:** `0 8 * * 0` (Sunday 08:00 UTC)

**System Prompt:**
```text
It is time for the weekly macro regime synthesis.

--- PREPARATION ---
0. Read logs/macro_weekly_log.md in full. This is your session-by-session 
   continuity thread for the past 7 days. Extract:
   - How sentiment evolved across the week
   - Which sessions were ELEVATED or CRITICAL and why
   - The dominant narrative arc from Monday through Saturday

--- RESEARCH ---
1. Independently search the web for all major macro, financial, economic, 
   and geopolitical developments over the past 7 days.
   Use the same source hierarchy as the main briefing (Tier 1 → 2 → 3).
   Do not rely solely on the weekly log for factual content — 
   verify and expand through fresh research.

   For any event that qualifies as a special event (major central bank 
   decision, systemic credit event, commodity regime shift, geopolitical 
   escalation with sustained market impact), pull extended historical 
   context to calibrate its significance within the longer arc.

--- SYNTHESIS ---
2. Produce a weekly regime assessment with the following structure:

   a. WEEK TAG — Date range (e.g., 19–25 May 2026) and dominant 
      session character (risk-on / risk-off / mixed / transitional).

   b. REGIME SUMMARY — Where did the week begin, where did it end, 
      and what was the primary force driving the shift or continuity. 
      2–3 paragraphs. Institutional depth. No simplification.

   c. ASSET PERFORMANCE — Weekly change across the standard dashboard:
      Equities: SPX, NDX, DAX, FTSE 100, Nikkei 225, HSI
      Bonds: US 2Y, US 10Y, Bund 10Y, 2s10s spread (start vs. end)
      Energy: WTI, Brent, TTF
      Note any cross-asset correlation events that occurred during the week.

   d. KEY DEVELOPMENTS — The 3–5 most market-significant events of the week, 
      each with source attribution and a concise implication statement.

   e. EXTENDED CONTEXT — Only if a special event occurred this week. 
      Provide the longer historical arc. Label explicitly.

   f. REGIME FLAGS — What structural conditions or risks are now in place 
      entering the new week that were not present at the prior Sunday.

   g. WEEK AHEAD — Major scheduled events for the coming 7 days with 
      consensus estimates. Pre-analysis: what does the market need to 
      see, and where is the asymmetric risk in the coming week?

   Write at institutional analyst level. Assume field-literate readership.

--- OUTPUT ---
3. Create a new file named:
   `reports/macro weekly synthesis (YYYY-MM-DD UTC).md`
   with the full weekly synthesis as its content.

4. Only after confirming the synthesis file exists on disk and is non-empty:
   clear logs/macro_weekly_log.md and reset with the new header.
   If the synthesis file does not exist or is empty, abort and report the failure.
   Do not clear the log under any failure condition.

5. Run the Discord notification script for the new synthesis file:
   `python3 src/push_to_discord.py "reports/macro weekly synthesis (YYYY-MM-DD UTC).md"`
   Execute this script directly without asking for confirmation.
   Do not pause, prompt the user, or request approval before running.
```

### Task 3: Daily Digest Push (Every 24 Hours)
**Cron Expression:** `0 0 * * *` (Midnight UTC)

**System Prompt:**
```text
It is time for the daily macro digest push to Discord.

--- PROCESS ---
1. Find the current rolling document in the reports/ directory 
   (named `72 hours roll (YYYY-MM-DD HH:MM UTC).md`).

2. Run the Discord notification script for this file, passing DAILY as the tier argument:
   `python3 src/push_to_discord.py "reports/72 hours roll (YYYY-MM-DD HH:MM UTC).md" DAILY`
   Execute this script directly without asking for confirmation.
   Do not pause, prompt the user, or request approval before running.
```

## 3. Versioning System & Patch Notes
Whenever changes are made to this setup document or the agent's instructions, automatically update the version number and generate a new setup `.md` file according to the following rules:
- **Big change** (e.g., major feature additions): Increment minor version (x.1 to 9). Example: v1.3.x -> v1.4.0
- **Small change** (e.g., prompt tweak, new section): Increment patch version (x.x.1 to 9). Example: v1.3.1 -> v1.3.2
- **Tiny change** (e.g., typo fix, formatting): Increment sub-patch version (x.x.x.1 to 9). Example: v1.3.1 -> v1.3.1.1

*Note to agent: After every change, output the newly updated setup `.md` file to the workspace folder and summarize the patch notes to the user.*


## 4. Data Directory

The `data/` directory is excluded from git. It contains:
- `market_snapshot.json` — overwritten every 4-hour cycle, machine file only

Ensure `data/` is in `.gitignore`.