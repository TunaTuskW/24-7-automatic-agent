import json
import os

new_code_cell = [
    "import sys\n",
    "import os\n",
    "sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))\n",
    "\n",
    "import json\n",
    "from src.schemas.models import MarketSnapshot\n",
    "\n",
    "# Find latest events.jsonl\n",
    "events_path = '../data/raw'\n",
    "part_dirs = []\n",
    "if os.path.exists(events_path):\n",
    "    for year in os.listdir(events_path):\n",
    "        yp = os.path.join(events_path, year)\n",
    "        if not os.path.isdir(yp): continue\n",
    "        for month in os.listdir(yp):\n",
    "            mp = os.path.join(yp, month)\n",
    "            for day in os.listdir(mp):\n",
    "                dp = os.path.join(mp, day)\n",
    "                part_dirs.append(dp)\n",
    "\n",
    "data = {}\n",
    "if part_dirs:\n",
    "    latest = sorted(part_dirs)[-1]\n",
    "    events_file = os.path.join(latest, 'events.jsonl')\n",
    "    if os.path.exists(events_file):\n",
    "        last_payload = None\n",
    "        with open(events_file, 'r') as f:\n",
    "            for line in f:\n",
    "                if not line.strip(): continue\n",
    "                try:\n",
    "                    evt = json.loads(line)\n",
    "                    if evt.get('event_type') == 'PipelineComplete':\n",
    "                        last_payload = evt.get('payload')\n",
    "                except: pass\n",
    "        if last_payload:\n",
    "            snapshot = MarketSnapshot.model_validate(last_payload)\n",
    "            data = snapshot.model_dump()\n",
    "print('Loaded latest MarketSnapshot from events.jsonl')\n"
]

for notebook in ["src/visualize_math_4h.ipynb", "src/visualize_math_1w.ipynb"]:
    if not os.path.exists(notebook):
        continue
    with open(notebook, 'r') as f:
        nb = json.load(f)
        
    for cell in nb.get("cells", []):
        if cell["cell_type"] == "code":
            # Check if this is the cell that loads market_snapshot or if it's our previous fix
            source = "".join(cell["source"])
            if "snapshot_path =" in source or "market_snapshot.json" in source or "events.jsonl" in source or "from src.schemas.models" in source:
                # Need to be careful not to rewrite everything if not necessary, but since our previous rewrite 
                # just contained the above code, replacing it again is perfectly safe.
                if "MarketSnapshot" in source and "sys.path.append" not in source:
                    cell["source"] = new_code_cell
                elif "snapshot_path =" in source:
                     cell["source"] = new_code_cell
                
    with open(notebook, 'w') as f:
        json.dump(nb, f, indent=1)
        
print("Updated notebooks with sys.path fix.")
