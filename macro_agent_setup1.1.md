# 24/7 Macro Analyst Agent Setup

This document contains the configuration used to create a 24/7 autonomous macro analyst using Agentic Scheduling. You can share this with any capable AI agent (like Opus 4.7) to recreate the exact same workflow.

## 1. The Target Artifact
Create a file named `daily_macro_briefing.md` with the following initial content:

```markdown
# 24/7 Global Macro & Market Briefing

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

**System Prompt / Instruction for the Background Task (v1.1):**
```text
It is time for the 24/7 global macro briefing update. 

1. Read the daily_macro_briefing.md artifact to find the timestamp of the very last update. 
2. Search the web for all major financial, economic, stock market, macro politics, and macroeconomic events that occurred *since that last timestamp* up to right now. This ensures no events are missed even if the system was offline/asleep. 
3. Analyze the findings with professional, institutional-grade insights. Focus on market implications and do not oversimplify.
4. Update the daily_macro_briefing.md artifact by appending a new timestamped section using your file editing tools.
5. (v1.1 Patch) Review the entire document and delete any updates or reports that have a timestamp older than 72 hours to maintain a rolling window and keep the document clean.
```
