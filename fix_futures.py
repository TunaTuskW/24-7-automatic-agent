with open("src/train_models.py", "r") as f:
    content = f.read()

import re
content = re.sub(r'es = data\["Close"\]\["ES=F"\].dropna\(\)\n.*?rty_ret = rty.pct_change\(\) \* 100', '', content, flags=re.DOTALL)
with open("src/train_models.py", "w") as f:
    f.write(content)
