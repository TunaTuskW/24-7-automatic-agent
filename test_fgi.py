import urllib.request
import json

url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        print(data['fear_and_greed']['score'])
except Exception as e:
    print("Failed:", e)
