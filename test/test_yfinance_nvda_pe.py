import yfinance as yf

# 以 Apple (AAPL) 为例
aapl = yf.Ticker("NVDA")
info = aapl.info
print(info)

# 尝试获取 Trailing P/E (TTE)
pe_ratio = info.get('forwardPE')
print(f"AAPL Trailing P/E: {pe_ratio}")