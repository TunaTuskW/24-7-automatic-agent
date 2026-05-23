# Macro Briefing Agent Setup Guide (v2.4.0)

This guide provides step-by-step instructions on how to set up the macro briefing agent, configure Discord notifications, and automate the execution using cron jobs.

## Project Structure Overview
Following the v2.0 refactor, the project is organized into dedicated folders:
- **`config/`**: Contains your API keys and webhook configurations (`fred_api_key.txt`, `webhook_config.txt`, etc.).
- **`src/`**: Houses the core Python code (`fetch_market_data.py`, `push_to_discord.py`, etc.).
- **`docs/`**: Documentation and agent setup prompts.
- **`data/`**: Local data files (e.g., market snapshots, models).
- **`reports/`**: Generated macro updates and weekly syntheses.
- **`logs/`**: Execution and error logs.
- **`older_versions/`**: Archived agent setup instructions.

## 1. Agent Setup

### Prerequisites
Ensure you have **Python 3** installed on your system. You will also need to install the required Python packages.

1. Open your terminal and navigate to the agent directory:
   ```bash
   cd /Users/mac/Downloads/agent
   ```
2. Install the required dependencies:
   ```bash
   pip3 install yfinance pandas numpy requests joblib arch
   ```

### API Keys
The agent requires a FRED (Federal Reserve Economic Data) API key to fetch specific market data (like treasury yields).

1. Go to the [FRED website](https://fred.stlouisfed.org/) and create an account to get a free API key.
2. Open the `config/fred_api_key.txt` file and paste your API key inside it.
   - Alternatively, you can set it as an environment variable: `export FRED_API_KEY="your_key"`

---

## 2. How to Set Up the Agent .md File

The core instructions for the macro analyst are stored in `docs/macro_agent_setup2.4.0.md`. This file contains the exact prompts, artifacts, and scheduling rules the agent follows. 

If you want an AI (like ChatGPT or Claude) to manually adopt this persona and run a cycle for you:
1. Open your AI assistant of choice.
2. Upload the `docs/macro_agent_setup2.4.0.md` file (or copy/paste its contents into the chat).
3. Say: *"Please read this setup document and execute Task 1 (the 4-hour briefing) using the latest market data."*
4. The AI will follow the exact structured analytical protocol outlined in the document.

---

## 3. How to Set Up Optional LLM

By default, the agent runs deterministically using local Python templates (`src/build_report.py`). However, the agent can optionally use an LLM API to generate advanced, natural-language narrative reports instead.

To enable the LLM generation:
1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/) (or an OpenAI/Anthropic key, depending on your script configuration).
2. Create or open the file `config/gemini_api_key.txt` and paste your API key inside it.
   *(If this file is missing or the API request fails, the agent will safely fall back to the standard deterministic templates).*

---

## 4. Discord Push Setup

The agent can push generated reports to a Discord channel using a webhook.

### Create a Webhook
1. Open Discord and go to the channel where you want the reports to be sent.
2. Click the gear icon next to the channel name to open **Edit Channel**.
3. Go to **Integrations** > **Webhooks** > **New Webhook**.
4. Name your webhook and click **Copy Webhook URL**.

### Configure the Agent
1. Open `config/webhook_config.txt` in the agent folder.
2. Paste your copied Webhook URL into this file and save it.
3. (Optional) If you want to ping a specific role for Elevated/Critical alerts, open `config/role_config.txt` and paste the Discord Role ID (e.g., `<@&1234567890>`). If left empty, it defaults to `@here`.

---

## 5. Cron Job Setup

To fully automate the agent, you can schedule the bash scripts using your system's cron daemon. `cron` runs silently in the background and executes scripts at specific times or intervals.

**Note on Sleep Mode:** 
Cron requires your Mac to be awake. If your Mac goes to sleep, the cron job will skip any scheduled runs that occur while asleep. It will resume once the Mac wakes up.

### Setting Up the Automation
1. Open your terminal and edit your crontab:
   ```bash
   crontab -e
   ```
2. Add the following entries to schedule the different reports. Make sure to use the absolute paths to the scripts.

   ```cron
   # Run the 4-hour automated pipeline (every 4 hours)
   0 */4 * * * /Users/mac/Downloads/agent/run_4h.sh >> /Users/mac/Downloads/agent/logs/cron.log 2>&1

   # Run the daily 72-hour roll push (every day at 8:00 AM)
   0 8 * * * /Users/mac/Downloads/agent/run_daily.sh >> /Users/mac/Downloads/agent/logs/cron.log 2>&1

   # Run the weekly synthesis pipeline (every Sunday at 10:00 AM)
   0 10 * * 0 /Users/mac/Downloads/agent/run_weekly.sh >> /Users/mac/Downloads/agent/logs/cron.log 2>&1
   ```
3. Save and exit the editor. Your cron jobs are now scheduled!

### How to "Catch Up"
If your Mac was asleep and missed a run, you can always catch up manually! Just open your terminal and run the exact absolute path for whichever script you missed (you don't need to change folders, just copy/paste these):
- Missed a 4-hour update? Run: `/Users/mac/Downloads/agent/run_4h.sh`
- Missed the daily Discord push? Run: `/Users/mac/Downloads/agent/run_daily.sh`
- Missed the Sunday weekly report? Run: `/Users/mac/Downloads/agent/run_weekly.sh`

### How to Pause or Remove the Automation
**To Pause (Temporarily Disable):**
1. Run `crontab -e`
2. Add a hashtag `#` at the beginning of the lines to comment them out.
3. Save and exit.

**To Remove Permanently:**
1. Run `crontab -e`
2. Delete the lines completely.
3. Save and exit.
*(Alternatively, running `crontab -r` in the terminal will wipe your entire schedule).*

---

## 6. Troubleshooting & Logs

Because Cron runs invisibly, you won't see pop-ups if it succeeds or fails. To check on it, you can view the log file. Both the Python scripts and your cron jobs will write out helpful error messages there.

Open Terminal and run this command to see the latest activity:
```bash
tail -n 20 /Users/mac/Downloads/agent/logs/cron.log
```
This will show you the output of the most recent automated runs!

## 7. Versioning System & Patch Notes
Whenever changes are made to this setup document, automatically update the version number in the title and summarize the patch notes to the user.
- **Big change** (e.g., major feature additions): Increment minor version (x.1 to 9). Example: v1.3.x -> v1.4.0
- **Small change** (e.g., prompt tweak, new section): Increment patch version (x.x.1 to 9). Example: v1.3.1 -> v1.3.2
- **Tiny change** (e.g., typo fix, formatting): Increment sub-patch version (x.x.x.1 to 9). Example: v1.3.1 -> v1.3.1.1

*Note to agent: After every change, ensure the title reflects the new version and summarize the patch notes to the user.*
