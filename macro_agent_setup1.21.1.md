# 24/7 Macro Analyst Agent Setup (v1.2.1)

This document contains the configuration used to create a 24/7 autonomous macro analyst using Agentic Scheduling. You can share this with any capable AI agent (like Opus 4.7) to recreate the exact same workflow.

## 1. The Target Artifact
Create a file named `daily_macro_briefing.md` with the following initial content:

```markdown
# 24/7 Global Macro & Market Briefing (v1.2.1)

This document contains professional, institutional-grade insights into major financial, economic, stock market, macro politics, and macroeconomic events. 
Updates are generated automatically **every 2 hours, 24/7**, seamlessly tracking the rolling global sessions (Asia, EU, and US).

---

## Latest Updates

*(Waiting for the first unified scheduled run...)*
```

## 2. The Scheduled Task Configuration
Use the agent's scheduling/cron capability to set up a recurring background task.

**Cron Expression:**
`0 */2 * * *` (Runs exactly every 2 hours, 24/7)

**System Prompt / Instruction for the Background Task (v1.2):**
```text
It is time for the 24/7 global macro briefing update.

--- PRE-RUN ---
0. Open daily_macro_briefing.md. Delete any timestamped section older than 72 hours. 
   This must be completed before any other step.

--- DATA COLLECTION ---
1. Identify the timestamp of the most recent remaining update in the document.

2. Collect all major macro, financial, economic, and geopolitical market events 
   that occurred since that timestamp up to now. Use the following source hierarchy 
   strictly in order — exhaust higher tiers before descending:

   TIER 1 (Primary — use first):
   Reuters, Associated Press, Federal Reserve (federalreserve.gov), ECB (ecb.europa.eu), 
   Bank of Japan (boj.or.jp), PBoC (pbc.gov.cn), BIS (bis.org), IMF (imf.org), 
   U.S. Bureau of Labor Statistics (bls.gov), U.S. Bureau of Economic Analysis (bea.gov), 
   Eurostat (ec.europa.eu/eurostat)

   TIER 2 (Contextual confirmation — use to verify or expand):
   Financial Times, Bloomberg (public), Wall Street Journal, Nikkei Asia, 
   South China Morning Post (markets)

   TIER 3 (Hard data points only):
   FRED (fred.stlouisfed.org), investing.com economic calendar, 
   BusinessWire / PRNewswire (major corporate earnings or guidance only)

   Do not use blogs, aggregators, social media, or opinion sites as sources.
   If a claim cannot be attributed to a Tier 1, 2, or 3 source, exclude it entirely.

--- ANALYSIS ---
3. Identify which market session this update covers (Asia, European, US, or inter-session).
   Apply the following analytical structure:

   a. SESSION TAG — Active or most recently closed session.
   b. DATA OBSERVATION — Key events and data releases, each with inline source attribution.
   c. MARKET IMPLICATION — Impact on equities, fixed income, FX, and/or commodities 
      where directly relevant. Do not speculate beyond what the data supports.
   d. RISK FLAGS — Developing tail risks, policy divergences, or breaks from prior consensus.
   e. CARRY-FORWARD — 1–2 items requiring monitoring in the next session.

   Write at institutional analyst level. Do not simplify. Do not editorialize without basis.

--- OUTPUT ---
4. Append a new section to daily_macro_briefing.md with the following format:

   ## [UTC Timestamp] — [Session Tag]
   **Sources used:** [list Tier 1/2/3 sources cited in this update]
   
   [Structured analysis per framework above]

   ---
```
