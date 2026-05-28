import yfinance as yf
for tk in ['^TNX', '^FVX', '^IRX']:
    ticker = yf.Ticker(tk)
    try:
        print(tk, ticker.history(period="1d")['Close'].iloc[-1])
    except:
        pass
