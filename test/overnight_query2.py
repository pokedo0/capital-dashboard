"""Yahoo Finance 夜盘数据获取工具 (简化版)"""
from curl_cffi import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import re, json

# 全局 Session 复用
_session = requests.Session(impersonate="chrome")

# 提取原始值的 lambda
_raw = lambda x: x.get("raw") if isinstance(x, dict) else x


def get_overnight(symbol: str) -> dict | None:
    """获取单个股票的夜盘数据"""
    try:
        resp = _session.get(f"https://finance.yahoo.com/quote/{symbol}", timeout=15)
        for m in re.finditer(r'"body":"(\{.*?quoteResponse.*?\})"', resp.text):
            try:
                data = json.loads(m.group(1).replace('\\"', '"').replace('\\\\', '\\'))
                q = data.get("quoteResponse", {}).get("result", [{}])[0]
                if "overnightMarketPrice" in q:
                    ts = _raw(q.get("overnightMarketTime"))
                    return {
                        "symbol": symbol,
                        "price": _raw(q.get("overnightMarketPrice")),
                        "change": _raw(q.get("overnightMarketChange")),
                        "pct": _raw(q.get("overnightMarketChangePercent")),
                        "time": datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else None,
                        "close": _raw(q.get("regularMarketPrice")),
                    }
            except: pass
    except Exception as e:
        print(f"[{symbol}] 错误: {e}")
    return None


def get_overnight_batch(symbols: list, workers: int = 5) -> list:
    """并发批量获取夜盘数据"""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [r for r in pool.map(get_overnight, symbols) if r]


def print_table(data: list):
    """打印表格"""
    print(f"\n{'股票':^6}{'夜盘价':>10}{'涨跌':>10}{'涨跌幅':>10}{'收盘价':>10}{'更新':>12}")
    print("-" * 60)
    for d in data:
        pct = f"{d['pct']:+.2f}%" if d['pct'] else "N/A"
        chg = f"{d['change']:+.2f}" if d['change'] else "N/A"
        print(f"{d['symbol']:^6}{d['price']:>10.2f}{chg:>10}{pct:>10}{d['close']:>10.2f}{d['time']:>12}")


if __name__ == "__main__":
    symbols = ["NVDA", "QQQ", "AAPL", "TSLA", "AMD"]
    print(f"获取 {len(symbols)} 个股票...")
    print_table(get_overnight_batch(symbols))
