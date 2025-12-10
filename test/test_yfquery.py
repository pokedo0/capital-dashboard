import yahooquery as yq
import pandas as pd
from typing import List

# 设置 pandas 显示选项，以便更好地查看 DataFrame
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# S&P 500 成分股列表的 URL
SP500_CSV_URL = (
    "https://jcoffi.github.io/index-constituents/constituents-sp500.csv"
)


def print_separator():
    """打印一个分隔符，使输出更清晰。"""
    print(f"{'-' * 40}\n")


def get_sp500_tickers() -> List[str]:
    """
    从指定的 URL 获取 S&P 500 股票代码列表。

    Returns:
        List[str]: 股票代码列表。
    """
    print(f"正在从 URL 获取 S&P 500 股票列表...\n{SP500_CSV_URL}")
    try:
        df = pd.read_csv(SP500_CSV_URL)
        # Yahoo Finance 使用 '-' 而不是 '.' 来表示某些股票 (例如 BRK.B -> BRK-B)
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        print(f"成功获取 {len(tickers)} 个股票代码。")
        return tickers
    except Exception as e:
        print(f"错误：无法从 URL 获取股票列表: {e}")
        return []

def get_price_changes(tickers: List[str]) -> pd.DataFrame:
    """
    获取指定股票代码列表的当日价格变动百分比。

    Args:
        tickers (List[str]): 股票代码列表。

    Returns:
        pd.DataFrame: 包含股票代码和价格变动百分比的 DataFrame。
                      如果发生错误，则返回一个空的 DataFrame。
    """
    try:
        # 使用 yahooquery 批量获取股票数据
        data = yq.Ticker(tickers).price
        df = pd.DataFrame.from_dict(data, orient='index')
        
        # 检查是否存在 regularMarketChangePercent 列
        if 'regularMarketChangePercent' in df.columns:
            # 提取 symbol 和 regularMarketChangePercent，并重命名
            df = df[['symbol', 'regularMarketChangePercent']]
            df = df.rename(columns={'regularMarketChangePercent': 'priceChangePercent'})
            return df
        else:
            print("警告: 返回的数据中不包含 'regularMarketChangePercent' 列")
            return pd.DataFrame()
    except Exception as e:
        print(f"获取股票数据时发生错误: {e}")
        return pd.DataFrame()


def main():
    """
    主函数：获取 S&P 500 所有股票的当日价格变动百分比。
    """
    sp500_tickers = get_sp500_tickers()
    if not sp500_tickers:
        print("无法继续，因为股票列表为空。")
        return

    print(f"\n开始一次性获取 {len(sp500_tickers)} 个股票的多种数据...")
    print("注意：一次性请求大量股票可能会因网络或API限制导致失败。")

    # 获取价格变动数据
    price_changes_df = get_price_changes(sp500_tickers)

    if not price_changes_df.empty:
        # 统计涨跌和平盘的数量
        涨的数量 = price_changes_df[price_changes_df['priceChangePercent'] > 0].shape[0]
        跌的数量 = price_changes_df[price_changes_df['priceChangePercent'] < 0].shape[0]
        平盘的数量 = price_changes_df[price_changes_df['priceChangePercent'] == 0].shape[0]

        print("\n涨跌统计:")
        print(f"上涨股票数量: {涨的数量}")
        print(f"下跌股票数量: {跌的数量}")
        print(f"平盘股票数量: {平盘的数量}")

        # 打印 DataFrame (只显示前几行)
        print("\n价格变动数据 (前 10 行):")
        print(price_changes_df.head(10))
    else:
        print("未能获取到任何股票的价格变动数据。")

if __name__ == "__main__":
    main()