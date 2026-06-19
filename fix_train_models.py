import re
with open("src/train_models.py", "r") as f:
    text = f.read()

# 1. Remove early stopping
text = text.replace('early_stopping=True', '')

# 2. Remove futures from tickers
text = text.replace('"ES=F", "NQ=F", "YM=F", "RTY=F", ', '')

# 3. Remove futures logic
es_logic = """    es = data["Close"]["ES=F"].dropna()
    es.index = pd.to_datetime(es.index).tz_localize(None)
    nq = data["Close"]["NQ=F"].dropna()
    nq.index = pd.to_datetime(nq.index).tz_localize(None)
    rty = data["Close"]["RTY=F"].dropna()
    rty.index = pd.to_datetime(rty.index).tz_localize(None)"""
text = text.replace(es_logic, "")

es_ret_logic = """    es = es[~es.index.duplicated(keep='last')]
    es_ret = es.pct_change() * 100
    nq = nq[~nq.index.duplicated(keep='last')]
    nq_ret = nq.pct_change() * 100
    rty = rty[~rty.index.duplicated(keep='last')]
    rty_ret = rty.pct_change() * 100"""
text = text.replace(es_ret_logic, "")

# 4. Remove from df
df_futures = """        "es_ret":        es_ret.reindex(spx_ret.index, method="ffill"),
        "nq_ret":        nq_ret.reindex(spx_ret.index, method="ffill"),
        "ym_ret":        ym_ret.reindex(spx_ret.index, method="ffill"),
        "rty_ret":       rty_ret.reindex(spx_ret.index, method="ffill"),
"""
text = text.replace(df_futures, "")

# 5. Remove from feature_names
text = text.replace('"es_ret", "nq_ret", "rty_ret", ', "")

with open("src/train_models.py", "w") as f:
    f.write(text)
