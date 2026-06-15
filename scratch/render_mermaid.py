import sys
import json
import base64
import urllib.request

def render():
    with open("README.md", "r") as f:
        lines = f.readlines()
    
    # Extract between ```mermaid and ```
    start = -1
    end = -1
    for i, line in enumerate(lines):
        if line.strip() == "```mermaid":
            start = i + 1
            break
    for i in range(start, len(lines)):
        if lines[i].strip() == "```":
            end = i
            break
            
    code = "".join(lines[start:end])
    
    # Mermaid ink standard base64 payload
    payload = json.dumps({"code": code, "mermaid": {"theme": "default"}})
    b64 = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')
    url = f"https://mermaid.ink/img/{b64}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open("reports/workflow_map.png", "wb") as f:
                f.write(response.read())
        print("Success! Downloaded to reports/workflow_map.png")
    except Exception as e:
        print(f"Failed to fetch from mermaid.ink: {e}")

if __name__ == "__main__":
    render()
