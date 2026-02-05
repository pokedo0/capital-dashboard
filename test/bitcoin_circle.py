"""
Bitcoin 4-Year Cycle Theory Backtest & Visualization
比特币4年周期理论回测与可视化

基于比特币减半周期（约4年），分析：
- 1年熊市阶段（红色区域）
- 3年牛市阶段（灰色区域）

数据源：Yahoo Finance (BTC-USD)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def fetch_bitcoin_data(start_date='2010-07-01', end_date=None):
    """
    从Yahoo Finance获取比特币数据
    BTC-USD 是比特币对美元的交易对
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"正在从Yahoo Finance获取BTC-USD数据...")
    print(f"时间范围: {start_date} 至 {end_date}")
    
    # 获取比特币数据
    btc = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)
    
    if btc.empty:
        raise ValueError("无法获取比特币数据，请检查网络连接")
    
    # 处理多层索引
    if isinstance(btc.columns, pd.MultiIndex):
        btc.columns = btc.columns.get_level_values(0)
    
    print(f"成功获取 {len(btc)} 条数据记录")
    return btc

def calculate_returns(df, window=365):
    """
    计算滚动收益率
    使用年化对数收益率
    """
    # 计算日收益率
    df['daily_return'] = df['Close'].pct_change()
    
    # 计算滚动年化收益率 (对数收益)
    df['log_return'] = np.log(df['Close'] / df['Close'].shift(1))
    df['rolling_annual_return'] = df['log_return'].rolling(window=window).sum()
    
    # 计算相对于历史的Z-score (标准化收益)
    df['return_zscore'] = (df['rolling_annual_return'] - df['rolling_annual_return'].expanding().mean()) / df['rolling_annual_return'].expanding().std()
    
    return df

def define_bitcoin_cycles():
    """
    定义比特币历史周期
    基于减半事件和历史价格周期
    
    比特币减半日期：
    - 第一次减半: 2012-11-28
    - 第二次减半: 2016-07-09
    - 第三次减半: 2020-05-11
    - 第四次减半: 2024-04-20 (预估)
    
    周期结构：
    - 熊市（1年）：从周期顶部到底部
    - 牛市（3年）：从底部到下一个顶部
    """
    
    cycles = [
        # 周期0 (2010-2011): 第一个早期周期
        {
            'name': 'Cycle 0',
            'bear_start': '2011-06-08',   # 第一次泡沫顶部 ~$32
            'bear_end': '2011-11-18',     # 底部 ~$2
            'bull_start': '2010-07-17',   # BTC开始有价格
            'bull_end': '2011-06-08',     # 顶部
            'cycle_label': '',
            'cycle_bottom': '2010-07-17'
        },
        # 周期1 (2011-2013): 
        {
            'name': 'Cycle 1',
            'bear_start': '2011-06-08',   # 顶部 ~$32
            'bear_end': '2011-11-18',     # 底部 ~$2
            'bull_start': '2011-11-18',
            'bull_end': '2013-11-29',     # 顶部 ~$1,100
            'cycle_label': '4Y',
            'cycle_bottom': '2011-11-18'
        },
        # 周期2 (2013-2017): 
        {
            'name': 'Cycle 2',
            'bear_start': '2013-11-29',   # 顶部 ~$1,100
            'bear_end': '2015-01-14',     # 底部 ~$170
            'bull_start': '2015-01-14',
            'bull_end': '2017-12-17',     # 顶部 ~$19,800
            'cycle_label': '4Y',
            'cycle_bottom': '2015-01-14'
        },
        # 周期3 (2017-2021):
        {
            'name': 'Cycle 3',
            'bear_start': '2017-12-17',   # 顶部 ~$19,800
            'bear_end': '2018-12-15',     # 底部 ~$3,200
            'bull_start': '2018-12-15',
            'bull_end': '2021-11-10',     # 顶部 ~$69,000
            'cycle_label': '4Y',
            'cycle_bottom': '2018-12-15'
        },
        # 周期4 (2021-2025+): 当前周期
        {
            'name': 'Cycle 4',
            'bear_start': '2021-11-10',   # 顶部 ~$69,000
            'bear_end': '2022-11-21',     # 底部 ~$15,500
            'bull_start': '2022-11-21',
            'bull_end': '2025-12-31',     # 预估顶部
            'cycle_label': '4Y?',
            'cycle_bottom': '2022-11-21'
        }
    ]
    
    return cycles

def create_cycle_chart(df, cycles):
    """
    创建类似图片的双轴周期图表
    """
    fig, ax1 = plt.subplots(figsize=(16, 9))
    
    # 设置深色背景
    fig.patch.set_facecolor('#1a1a2e')
    ax1.set_facecolor('#1a1a2e')
    
    # 第二个Y轴 (比特币价格)
    ax2 = ax1.twinx()
    
    # 绘制周期背景
    for cycle in cycles:
        # 熊市区域 (红色/暗红)
        bear_start = pd.to_datetime(cycle['bear_start'])
        bear_end = pd.to_datetime(cycle['bear_end'])
        
        if bear_start >= df.index.min():
            ax1.axvspan(bear_start, bear_end, alpha=0.4, color='#8B0000', zorder=0)
            
            # 添加 "1Y" 标签
            mid_bear = bear_start + (bear_end - bear_start) / 2
            ax1.text(mid_bear, ax1.get_ylim()[1] * 0.95 if ax1.get_ylim()[1] > 0 else 11, 
                    '1Y', ha='center', va='top', fontsize=14, color='white', fontweight='bold')
        
        # 牛市区域 (灰色)
        bull_start = pd.to_datetime(cycle['bull_start'])
        bull_end = pd.to_datetime(cycle['bull_end'])
        
        if bull_start >= df.index.min() and bull_end <= df.index.max() + timedelta(days=365):
            ax1.axvspan(bull_start, min(bull_end, df.index.max()), 
                       alpha=0.3, color='#4a4a6a', zorder=0)
            
            # 添加 "3Y" 标签
            mid_bull = bull_start + (min(bull_end, df.index.max()) - bull_start) / 2
            label = '3Y?' if cycle['name'] == 'Cycle 4' else '3Y'
            ax1.text(mid_bull, 11, label, ha='center', va='top', 
                    fontsize=14, color='white', fontweight='bold')
    
    # 绘制收益率曲线 (左Y轴) - 橙色
    valid_data = df.dropna(subset=['return_zscore'])
    ax1.plot(valid_data.index, valid_data['return_zscore'], 
             color='#FFA500', linewidth=1.5, label='收益率 Z-Score', zorder=3)
    
    # 绘制比特币价格 (右Y轴) - 白色，使用对数刻度
    ax2.semilogy(df.index, df['Close'], color='white', linewidth=1.2, 
                 label='BTC价格 (USD)', zorder=3)
    
    # 绘制周期底部弧线 (橙色虚线)
    for cycle in cycles:
        bottom_date = pd.to_datetime(cycle['cycle_bottom'])
        next_bottom = None
        
        # 找到下一个周期底部
        cycle_idx = cycles.index(cycle)
        if cycle_idx < len(cycles) - 1:
            next_bottom = pd.to_datetime(cycles[cycle_idx + 1]['cycle_bottom'])
        else:
            next_bottom = bottom_date + timedelta(days=4*365)  # 估计4年后
        
        if bottom_date >= df.index.min():
            # 创建弧线数据
            arc_dates = pd.date_range(start=bottom_date, end=min(next_bottom, df.index.max()), periods=100)
            
            # 使用正弦函数创建弧线
            x = np.linspace(0, np.pi, len(arc_dates))
            arc_values = -2 - 1.5 * np.sin(x)  # 底部弧线
            
            ax1.plot(arc_dates, arc_values, color='#FFA500', linewidth=2, 
                    linestyle='-', alpha=0.8, zorder=2)
            
            # 添加 "4Y" 标签
            mid_point = len(arc_dates) // 2
            label = cycle['cycle_label']
            ax1.text(arc_dates[mid_point], -3.8, label, ha='center', va='top',
                    fontsize=12, color='white', fontweight='bold')
    
    # 设置坐标轴
    ax1.set_ylabel('收益率 Z-Score', color='#FFA500', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='#FFA500')
    ax1.set_ylim(-4, 12)
    
    ax2.set_ylabel('BTC 价格 (USD)', color='white', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='white')
    
    # 设置X轴
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax1.tick_params(axis='x', colors='white')
    
    # 设置网格
    ax1.grid(True, alpha=0.2, color='gray', linestyle='-', zorder=1)
    ax1.set_axisbelow(True)
    
    # 添加水平参考线
    ax1.axhline(y=0, color='gray', linestyle='-', alpha=0.5, linewidth=1)
    ax1.axhline(y=-2, color='gray', linestyle='--', alpha=0.3, linewidth=1)
    
    # 设置标题
    plt.title('比特币 4年周期理论分析\nBitcoin 4-Year Cycle Analysis', 
              color='white', fontsize=16, fontweight='bold', pad=20)
    
    # 添加图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', 
              facecolor='#2a2a4a', edgecolor='gray', labelcolor='white')
    
    # 添加版权信息
    fig.text(0.02, 0.02, f'数据来源: Yahoo Finance | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 
             color='gray', fontsize=8)
    
    # 设置边框颜色
    for spine in ax1.spines.values():
        spine.set_color('gray')
    for spine in ax2.spines.values():
        spine.set_color('gray')
    
    plt.tight_layout()
    return fig

def calculate_cycle_statistics(df, cycles):
    """
    计算每个周期的统计数据
    """
    stats = []
    
    for cycle in cycles:
        bear_start = pd.to_datetime(cycle['bear_start'])
        bear_end = pd.to_datetime(cycle['bear_end'])
        bull_start = pd.to_datetime(cycle['bull_start'])
        bull_end = pd.to_datetime(cycle['bull_end'])
        
        # 确保日期在数据范围内
        if bear_start < df.index.min():
            continue
        
        cycle_stats = {
            'name': cycle['name'],
            'bear_start': bear_start.strftime('%Y-%m-%d'),
            'bear_end': bear_end.strftime('%Y-%m-%d'),
        }
        
        # 计算熊市统计
        if bear_start in df.index or bear_start >= df.index.min():
            bear_data = df[(df.index >= bear_start) & (df.index <= bear_end)]
            if len(bear_data) > 0:
                cycle_stats['bear_peak_price'] = bear_data['Close'].iloc[0]
                cycle_stats['bear_bottom_price'] = bear_data['Close'].min()
                cycle_stats['bear_drawdown'] = (cycle_stats['bear_bottom_price'] / cycle_stats['bear_peak_price'] - 1) * 100
        
        # 计算牛市统计
        if bull_end <= df.index.max():
            bull_data = df[(df.index >= bull_start) & (df.index <= min(bull_end, df.index.max()))]
            if len(bull_data) > 0:
                cycle_stats['bull_start_price'] = bull_data['Close'].iloc[0]
                cycle_stats['bull_peak_price'] = bull_data['Close'].max()
                cycle_stats['bull_return'] = (cycle_stats['bull_peak_price'] / cycle_stats['bull_start_price'] - 1) * 100
        
        stats.append(cycle_stats)
    
    return stats

def main():
    """
    主函数
    """
    print("=" * 60)
    print("比特币 4年周期理论回测分析")
    print("Bitcoin 4-Year Cycle Theory Backtest")
    print("=" * 60)
    
    # 1. 获取数据
    df = fetch_bitcoin_data(start_date='2010-07-01')
    
    # 2. 计算收益率指标
    df = calculate_returns(df, window=365)
    
    # 3. 定义周期
    cycles = define_bitcoin_cycles()
    
    # 4. 计算周期统计
    print("\n" + "=" * 60)
    print("周期统计分析")
    print("=" * 60)
    
    stats = calculate_cycle_statistics(df, cycles)
    for stat in stats:
        print(f"\n{stat['name']}:")
        print(f"  熊市期间: {stat['bear_start']} 至 {stat['bear_end']}")
        if 'bear_drawdown' in stat:
            print(f"  熊市最大回撤: {stat['bear_drawdown']:.1f}%")
            print(f"  顶部价格: ${stat['bear_peak_price']:.2f}")
            print(f"  底部价格: ${stat['bear_bottom_price']:.2f}")
        if 'bull_return' in stat:
            print(f"  牛市收益: {stat['bull_return']:.1f}%")
            print(f"  牛市顶部价格: ${stat['bull_peak_price']:.2f}")
    
    # 5. 创建图表
    print("\n正在生成图表...")
    fig = create_cycle_chart(df, cycles)
    
    # 保存图表
    output_path = 'd:/Program/java_project/capitalDashboard2/test/bitcoin_4year_cycle.png'
    fig.savefig(output_path, dpi=150, facecolor='#1a1a2e', edgecolor='none', bbox_inches='tight')
    print(f"图表已保存至: {output_path}")
    
    # 显示图表
    plt.show()
    
    print("\n" + "=" * 60)
    print("分析完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
