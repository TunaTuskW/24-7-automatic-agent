import yfinance as yf
from src.engines.feature_engine import ALL_YF_TICKERS
tickers = list(ALL_YF_TICKERS.values())
raw_df = yf.download(tickers, period="30d", interval="1d", group_by="ticker", progress=False, threads=True)
print("MultiIndex?", hasattr(raw_df.columns, "levels"))
if hasattr(raw_df.columns, "levels"):
    print("Levels[0]:", raw_df.columns.levels[0][:5])
    print("Levels[1]:", raw_df.columns.levels[1][:5])
found = []
for name, tk in ALL_YF_TICKERS.items():
    if tk in raw_df.columns.levels[0]:
        found.append(tk)
print("Found tickers count:", len(found))
