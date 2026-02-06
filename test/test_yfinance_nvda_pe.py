# import yfinance as yf

# # 以 Apple (AAPL) 为例
# aapl = yf.Ticker("NVDA")
# info = aapl.info
# print(info)

# # 尝试获取 Trailing P/E (TTE)
# pe_ratio = info.get('forwardPE')
# print(f"AAPL Trailing P/E: {pe_ratio}")


import requests

url = "https://query1.finance.yahoo.com/v7/finance/quote"
params = {"symbols": "NVDA"}

r = requests.get(url, params=params)
data = r.json()["quoteResponse"]["result"][0]

overnight = {
    "price": data.get("overnightMarketPrice"),
    "change": data.get("overnightMarketChange"),
    "pct": data.get("overnightMarketChangePercent"),
    "time": data.get("overnightMarketTime"),
}

print(overnight)