import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd

# 1. 设置时间范围 (获取过去5年的数据，以观察这一波集中度的趋势)
start_date = '2015-01-01'
end_date = pd.Timestamp.now().strftime('%Y-%m-%d')

# 2. 下载数据 (SPY 和 RSP)
print("正在下载数据...")
tickers = ['SPY', 'RSP']
data = yf.download(tickers, start=start_date, end=end_date)['Close']

# 3. 计算比值 (SPY / RSP)
# 这个比值越高，代表市值最大的几只股票（如Mag 7）涨得越好，而其餘普通股票表现平平
data['Ratio'] = data['SPY'] / data['RSP']

# 4. 绘图
plt.figure(figsize=(12, 6))

# 绘制比值曲线
plt.plot(data.index, data['Ratio'], label='SPY / RSP Ratio', color='#2ecc71', linewidth=2)

# 添加 3.5 指标线 (图片中的警戒线)
plt.axhline(y=3.5, color='gray', linestyle='--', linewidth=1.5, label='3.5 指标线')

# 添加当前最新比值的标注 (模仿图中样式)
latest_date = data.index[-1]
latest_ratio = data['Ratio'].iloc[-1]
latest_spy = data['SPY'].iloc[-1]
latest_rsp = data['RSP'].iloc[-1]

# 在图表上标注最新的数值
plt.annotate(f'{latest_ratio:.3f}',
             xy=(latest_date, latest_ratio),
             xytext=(latest_date, latest_ratio + 0.1),
             arrowprops=dict(facecolor='black', shrink=0.05),
             fontsize=14, fontweight='bold', color='green')

# 标题和标签
plt.title(f'SPY / RSP Ratio Trend (Market Concentration)\nCurrent: {latest_spy:.0f}/{latest_rsp:.0f} = {latest_ratio:.3f}', fontsize=16)
plt.ylabel('Ratio (SPY Price / RSP Price)', fontsize=12)
plt.xlabel('Date', fontsize=12)
plt.grid(True, alpha=0.3)
plt.legend()

# 显示图表
plt.tight_layout()
plt.show()