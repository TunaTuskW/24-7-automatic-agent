import os
import glob
import re

old_block = """    snapshot_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_snapshot.json')
    if not os.path.exists(snapshot_path):
        print(f"Error: {snapshot_path} not found. Run fetch_market_data.py first.")
        return

    with open(snapshot_path, 'r') as f:
        data = json.load(f)"""

new_block = """    events_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    part_dirs = []
    if os.path.exists(events_path):
        for year in os.listdir(events_path):
            year_path = os.path.join(events_path, year)
            if not os.path.isdir(year_path): continue
            for month in os.listdir(year_path):
                month_path = os.path.join(year_path, month)
                for day in os.listdir(month_path):
                    day_path = os.path.join(month_path, day)
                    part_dirs.append(day_path)
    if not part_dirs:
        print("Error: No event data found.")
        return
    latest_part = sorted(part_dirs)[-1]
    events_file = os.path.join(latest_part, "events.jsonl")
    if not os.path.exists(events_file): return
    last_snapshot_payload = None
    import json
    with open(events_file, 'r') as f:
        for line in f:
            if not line.strip(): continue
            try:
                evt = json.loads(line)
                if evt.get("event_type") == "PipelineComplete":
                    last_snapshot_payload = evt.get("payload")
            except: pass
    if not last_snapshot_payload: return
    from src.schemas.models import MarketSnapshot
    snapshot = MarketSnapshot.model_validate(last_snapshot_payload)
    data = snapshot.model_dump()"""

for fpath in ["src/build_weekly_synthesis.py", "src/build_72h_roll.py"]:
    if os.path.exists(fpath):
        with open(fpath, "r") as f:
            content = f.read()
        if "market_snapshot.json" in content:
            content = re.sub(r"    snapshot_path.*json\.load\(f\)", new_block, content, flags=re.DOTALL)
            with open(fpath, "w") as f:
                f.write(content)
            print(f"Updated {fpath}")

# Jupyter Notebooks
for fpath in ["src/visualize_math_4h.ipynb", "src/visualize_math_1w.ipynb"]:
    if os.path.exists(fpath):
        with open(fpath, "r") as f:
            content = f.read()
        if "market_snapshot.json" in content:
            # Simple replacement
            content = content.replace("market_snapshot.json", "raw/.../events.jsonl")
            with open(fpath, "w") as f:
                f.write(content)
            print(f"Updated {fpath}")
