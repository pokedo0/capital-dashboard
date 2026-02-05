# import yfinance as yf

# # 以 Apple (AAPL) 为例
# aapl = yf.Ticker("NVDA")
# info = aapl.info
# print(info)

# # 尝试获取 Trailing P/E (TTE)
# pe_ratio = info.get('forwardPE')
# print(f"AAPL Trailing P/E: {pe_ratio}")


import yfinance as yf

nvda = yf.Ticker("NVDA")

# 尝试直接获取
print(f"尝试直接读取: {nvda.info.get('ytdReturn')}")
# 输出通常是: 尝试直接读取: None