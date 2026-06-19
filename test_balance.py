import numpy as np
import yfinance as yf
df = yf.download('^GSPC', start='2020-01-01', end='2026-06-01', interval='1d', progress=False)
fwd_periods = 5
threshold = 1.5
forward_5d = df['Close'].squeeze().pct_change().shift(-fwd_periods).rolling(fwd_periods).sum().fillna(0) * 100
y = np.where(forward_5d > threshold, 1, np.where(forward_5d < -threshold, 0, 2))
import pandas as pd
print("Class counts for SPX:")
print(pd.Series(y).value_counts(normalize=True) * 100)
