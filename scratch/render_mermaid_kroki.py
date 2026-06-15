import sys
import zlib
import base64
import urllib.request

def kroki_encode(text):
    compressed = zlib.compress(text.encode('utf-8'), 9)
    # kroki uses base64url encoding
    return base64.urlsafe_b64encode(compressed).decode('utf-8')

def render():
    with open("README.md", "r") as f:
        lines = f.readlines()
    
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
    
    encoded = kroki_encode(code)
    url = f"https://kroki.io/mermaid/png/{encoded}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open("reports/workflow_map.png", "wb") as f:
                f.write(response.read())
        print("Success! Downloaded to reports/workflow_map.png")
    except Exception as e:
        print(f"Failed to fetch from kroki.io: {e}")

if __name__ == "__main__":
    render()
