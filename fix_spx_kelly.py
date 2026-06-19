with open("src/engines/risk_engine.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "spx_raw = raw_allocations.get(\"spx\", 0.0)" in line:
        new_lines.append("        spx_kelly = 0.0\n")

with open("src/engines/risk_engine.py", "w") as f:
    f.writelines(new_lines)
