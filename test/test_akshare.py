import pandas as pd
from typing import List

# 尝试导入 akshare，如果不存在则提示用户
try:
    import akshare as ak
except ImportError:
    print("错误: 未找到 'akshare' 模块。请先运行 'pip install akshare' 安装。")
    exit(1)

# 设置 pandas 显示选项
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# S&P 500 成分股列表的 URL
SP500_CSV_URL = (
    "https://jcoffi.github.io/index-constituents/constituents-sp500.csv"
)

def get_sp500_tickers() -> List[str]:
    """
    从指定的 URL 获取 S&P 500 股票代码列表。
    """
    print(f"正在从 URL 获取 S&P 500 股票列表...\n{SP500_CSV_URL}")
    try:
        df = pd.read_csv(SP500_CSV_URL)
        # 统一格式，例如 BRK.B -> BRK-B
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        print(f"成功获取 {len(tickers)} 个股票代码。")
        return tickers
    except Exception as e:
        print(f"错误：无法从 URL 获取股票列表: {e}")
        return []

def get_price_changes(tickers: List[str]) -> pd.DataFrame:
    """
    使用 AkShare 获取美股实时行情，并筛选出 S&P 500 成分股的数据。
    尝试使用 东方财富 (EM) 接口，失败则尝试 新浪 (Sina) 接口。
    """
    print(f"AkShare version: {ak.__version__}")
    
    # --- 尝试 1: 东方财富 (EastMoney) ---
    print("正在调用 AkShare 获取美股实时行情 (stock_us_spot_em)...")
    try:
        spot_df = ak.stock_us_spot_em()
        # 东方财富列名映射
        col_map = {}
        if '代码' in spot_df.columns: col_map['代码'] = 'symbol'
        if '涨跌幅' in spot_df.columns: col_map['涨跌幅'] = 'priceChangePercent'
        
        # 英文列名兼容
        if 'symbol' in spot_df.columns: col_map['symbol'] = 'symbol'
        if 'pct_chg' in spot_df.columns: col_map['pct_chg'] = 'priceChangePercent'

        spot_df = spot_df.rename(columns=col_map)
        
        if 'symbol' in spot_df.columns and 'priceChangePercent' in spot_df.columns:
            spot_df['symbol'] = spot_df['symbol'].astype(str).str.upper()
            # 过滤
            filtered_df = spot_df[spot_df['symbol'].isin(tickers)].copy()
            # 转换百分比 (EM 返回的是百分比数值，如 1.5)
            filtered_df['priceChangePercent'] = pd.to_numeric(filtered_df['priceChangePercent'], errors='coerce') / 100.0
            return filtered_df[['symbol', 'priceChangePercent']]
        else:
            print("EM 接口返回列名不匹配，尝试备用接口...")
            
    except Exception as e:
        print(f"EM 接口调用失败: {e}")
        print("尝试切换到新浪接口...")

    # --- 尝试 2: 新浪 (Sina) ---
    print("正在调用 AkShare 获取美股实时行情 (stock_us_spot)...")
    try:
        spot_df = ak.stock_us_spot()
        # 打印前几行以检查数据结构 (调试用)
        # print("Sina Raw Data Head:", spot_df[['symbol', 'price', 'chg', 'diff']].head())

        # 新浪返回列名: ['name', 'cname', 'category', 'symbol', 'price', 'diff', 'chg', ...]
        # 通常 'chg' 是涨跌幅 (百分比), 'diff' 是涨跌额
        
        col_map = {}
        if 'symbol' in spot_df.columns: col_map['symbol'] = 'symbol'
        if 'chg' in spot_df.columns: col_map['chg'] = 'priceChangePercent'
        if 'percent' in spot_df.columns: col_map['percent'] = 'priceChangePercent'
        
        spot_df = spot_df.rename(columns=col_map)

        if 'symbol' in spot_df.columns and 'priceChangePercent' in spot_df.columns:
             spot_df['symbol'] = spot_df['symbol'].astype(str).str.upper()
             
             # 打印未过滤前的数据，方便确认单位
             # print("Renamed Data Head:", spot_df[['symbol', 'priceChangePercent']].head())

             filtered_df = spot_df[spot_df['symbol'].isin(tickers)].copy()
             
             # 假设 chg 是百分比 (如 1.23 代表 1.23%)，需要除以 100
             filtered_df['priceChangePercent'] = pd.to_numeric(filtered_df['priceChangePercent'], errors='coerce') / 100.0
             return filtered_df[['symbol', 'priceChangePercent']]
        else:
             print("Sina 接口返回列名不匹配:", spot_df.columns.tolist())

    except Exception as e:
        print(f"Sina 接口调用失败: {e}")

    return pd.DataFrame()

def main():
    sp500_tickers = get_sp500_tickers()
    if not sp500_tickers:
        return

    price_changes_df = get_price_changes(sp500_tickers)

    if not price_changes_df.empty:
        # 统计
        涨的数量 = price_changes_df[price_changes_df['priceChangePercent'] > 0].shape[0]
        跌的数量 = price_changes_df[price_changes_df['priceChangePercent'] < 0].shape[0]
        平盘的数量 = price_changes_df[price_changes_df['priceChangePercent'] == 0].shape[0]

        print("\n涨跌统计 (AkShare):")
        print(f"上涨股票数量: {涨的数量}")
        print(f"下跌股票数量: {跌的数量}")
        print(f"平盘股票数量: {平盘的数量}")
        print(f"覆盖股票数量: {len(price_changes_df)} / {len(sp500_tickers)}")

        print("\n价格变动数据 (前 10 行):")
        print(price_changes_df.head(10))
    else:
        print("未能获取到数据。")

if __name__ == "__main__":
    main()
