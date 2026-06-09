import yfinance as yf
data = yf.download(["^GSPC", "GC=F"], start="2025-11-01", end="2026-06-05", group_by="ticker")
print("GC=F NaN count:", data["GC=F"]["Close"].isna().sum())
print("GSPC NaN count:", data["^GSPC"]["Close"].isna().sum())
