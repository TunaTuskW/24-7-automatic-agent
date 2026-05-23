# Cron Job Setup Guide

This guide explains how to fully automate the Macro Agent pipeline using a standard macOS/Linux `cron` job. By setting this up, your Mac will automatically fetch data, build the markdown reports, and push them to Discord without any manual intervention.

## 1. What is Cron?
`cron` is a built-in time-based job scheduler on Unix-like operating systems (including macOS). It runs silently in the background and executes scripts at specific times or intervals.

**Note on Sleep Mode:** 
Cron requires your Mac to be awake. If your Mac goes to sleep, the cron job will skip any scheduled runs that occur while asleep. It will resume once the Mac wakes up.

**How to "Catch Up":**
If your Mac was asleep and missed a run, you can always catch up manually! Just open your terminal and run the exact absolute path for whichever script you missed (you don't need to change folders, just copy/paste these):
- Missed a 4-hour update? Run: `/Users/mac/agent/run_4h.sh`
- Missed the daily Discord push? Run: `/Users/mac/agent/run_daily.sh`
- Missed the Sunday weekly report? Run: `/Users/mac/agent/run_weekly.sh`

---

## 2. Setting Up the Automation

### Step 1: Open the Cron Editor
Open your **Terminal** and run:
```bash
crontab -e
```
*Tip: If the editor feels confusing (it defaults to `vim`), you can press `Esc`, type `:q!` and hit Enter to quit. Then run `export EDITOR=nano` before running `crontab -e` again to use a simpler editor.*

### Step 2: Add the Schedule
Once the editor is open, use your arrow keys to go to the very bottom and paste these exact lines to set up all three jobs (4-Hour, Daily, and Weekly):

```bash
# 1. Main 4-Hour Briefing (Runs at minute 0 past every 4th hour)
0 */4 * * * /Users/mac/agent/run_4h.sh >> /Users/mac/agent/logs/cron.log 2>&1

# 2. Daily Digest Push (Runs at Midnight UTC / 7:00 AM local)
0 0 * * * /Users/mac/agent/run_daily.sh >> /Users/mac/agent/logs/cron.log 2>&1

# 3. Weekly Synthesis (Runs every Sunday at 08:00 UTC / 3:00 PM local)
0 8 * * 0 /Users/mac/agent/run_weekly.sh >> /Users/mac/agent/logs/cron.log 2>&1
```

### Step 3: Save and Exit
- If you are using **`nano`**: Press `Ctrl + O`, hit `Enter` to save, then press `Ctrl + X` to exit.
- If you are using **`vim`**: Press `Esc`, type `:wq`, and hit `Enter`.

You should see the message: `crontab: installing new crontab`. This means it was successful!

---

## 3. How to Pause or Remove the Automation

### To Pause (Temporarily Disable):
1. Run `crontab -e`
2. Add a hashtag `#` at the beginning of the lines to comment them out.
3. Save and exit.

### To Remove Permanently:
1. Run `crontab -e`
2. Delete the lines completely.
3. Save and exit.
*(Alternatively, if these are your only cron jobs, running `crontab -r` in the terminal will wipe your entire schedule).*

---

## 4. Troubleshooting & Logs

Because Cron runs invisibly, you won't see pop-ups if it succeeds or fails. To check on it, you can view the log file.

Open Terminal and run this command to see the latest activity:
```bash
tail -n 20 /Users/mac/agent/logs/cron.log
```
This will show you the output of the most recent automated runs!
