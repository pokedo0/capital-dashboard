

from __future__ import annotations

from datetime import datetime



import barchart_api

# Approximate number of daily records to cover ~3 months of trading.
THREE_MONTH_RECORDS = 90


def _parse_stock_row(row: str) -> dict[str, object]:
    """
    Barchart 的 timeseries 接口返回 CSV 行，字段顺序如下：
    symbol,date,open,high,low,close,volume
    """
    columns = row.split(",")
    if len(columns) != 7:
        raise AssertionError(f"返回格式异常：{row}")
    symbol, raw_date, opn, high, low, close, volume = columns
    return {
        "symbol": symbol,
        "date": datetime.strptime(raw_date, "%Y-%m-%d"),
        "open": float(opn),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": int(volume),
    }


def test_can_fetch_ndth_stock_timeseries() -> None:
    client = barchart_api.Api()
    response = client.get_stock(symbol="$NDTH", max_records=THREE_MONTH_RECORDS)

    assert response.status_code == 200, f"HTTP 状态码异常: {response.status_code}"

    rows = [line for line in response.text.splitlines() if line.strip()]
    assert rows, "返回内容为空"

    parsed_rows = [_parse_stock_row(row) for row in rows]
    assert {row["symbol"] for row in parsed_rows} == {"$NDTH"}

    latest_row = parsed_rows[0]
    assert latest_row["high"] >= latest_row["low"], "最高价应该大于等于最低价"
    assert latest_row["volume"] > 0, "成交量应为正数"


if __name__ == "__main__":
    client = barchart_api.Api()
    response = client.get_stock(symbol="$NDTH", max_records=THREE_MONTH_RECORDS)
    rows = [line for line in response.text.splitlines() if line.strip()]

    print("原始响应：")
    print(response.text)

    print("\n结构化结果：")
    for parsed in (_parse_stock_row(row) for row in rows):
        print(parsed)
