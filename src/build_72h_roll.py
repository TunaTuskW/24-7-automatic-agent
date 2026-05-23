#!/usr/bin/env python3
import os
import glob
import re
from datetime import datetime, timezone, timedelta

def main():
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    updates_dir = os.path.join(reports_dir, 'updates')
    
    if not os.path.exists(updates_dir):
        print("No updates directory found.")
        return

    # Target Upgrade v2.7.1: Separate roll compiling from file deletion
    now_utc = datetime.now(timezone.utc)
    cutoff_time_roll = now_utc - timedelta(hours=72)     # Roll only the last 72 hours
    cutoff_time_delete = now_utc - timedelta(hours=168)  # Retain files for 7 days (168 hours)
    
    update_files = glob.glob(os.path.join(updates_dir, '4 hours update (*).md'))
    valid_updates = []
    
    # Parse timestamps from filenames
    pattern = re.compile(r'4 hours update \(([\d]{4}-[\d]{2}-[\d]{2} [\d]{2}:[\d]{2}) UTC\)\.md')
    
    for fpath in update_files:
        fname = os.path.basename(fpath)
        match = pattern.search(fname)
        if match:
            dt_str = match.group(1)
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                dt = dt.replace(tzinfo=timezone.utc)
                
                # Check if the file belongs in the 72-hour roll
                if dt >= cutoff_time_roll:
                    valid_updates.append((dt, fpath))
                
                # Check if the file is older than 7 days and should be deleted
                elif dt < cutoff_time_delete:
                    os.remove(fpath)
                    print(f"Deleted old update (7-day retention cutoff): {fname}")
            except ValueError:
                pass

    valid_updates.sort(key=lambda x: x[0], reverse=True) # newest first
    
    if not valid_updates:
        print("No recent updates to roll.")
        return

    # Delete old 72 hours roll files
    old_rolls = glob.glob(os.path.join(reports_dir, '72 hours roll (*).md'))
    for old in old_rolls:
        os.remove(old)

    latest_dt_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    roll_filename = f"72 hours roll ({latest_dt_str}).md"
    roll_path = os.path.join(reports_dir, roll_filename)

    with open(roll_path, 'w') as out_f:
        out_f.write(f"```text\n[ 72 HOURS ROLLING MACRO UPDATE ]\nGenerated at: {latest_dt_str}\n```\n\n")
        
        for dt, fpath in valid_updates:
            with open(fpath, 'r') as in_f:
                content = in_f.read()
                out_f.write(content)
                out_f.write("\n\n")
                
    print(f"Created {roll_filename} with {len(valid_updates)} recent updates.")

if __name__ == "__main__":
    main()
