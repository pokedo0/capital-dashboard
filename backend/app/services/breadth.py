from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Dict, List, Sequence, Tuple

import barchart_api
from sqlmodel import Session, select

from ..core.config import get_settings
from ..models.price import PriceRecord
from ..schemas.market import MarketBreadthResponse, RelativeSeries, ValuePoint
from .market_data import ensure_history
from .time_ranges import resolve_range_end, resolve_range_start

logger = logging.getLogger(__name__)
settings = get_settings()


def _parse_barchart_rows(text: str) -> List[Tuple[date, float]]:
    rows: List[Tuple[date, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        if parts[0].lower() == "symbol":
            continue
        try:
            parsed_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
            close_value = float(parts[5])
        except ValueError:
            continue
        rows.append((parsed_date, close_value))
    rows.sort(key=lambda row: row[0])
    return rows


def _to_relative_points(series: List[Tuple[date, float]]) -> List[ValuePoint]:
    return [
        ValuePoint(time=entry_date, value=value)
        for entry_date, value in series
        if value is not None
    ]


def _load_benchmark(session: Session, start_date: date, end_date: date) -> Tuple[List[ValuePoint], List[ValuePoint]]:
    ensure_history(session, "^NDX", start_date, end_date)
    records = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == "^NDX")
            .where(PriceRecord.trade_date.between(start_date, end_date))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    pairs: List[Tuple[date, float]] = []
    price_points: List[ValuePoint] = []
    for record in records:
        if record.close is None:
            continue
        pairs.append((record.trade_date, record.close))
        price_points.append(ValuePoint(time=record.trade_date, value=record.close))
    return _to_relative_points(pairs), price_points


def _estimate_records(start_date: date, end_date: date) -> int:
    days = (end_date - start_date).days
    # 留出 10 天缓冲，避免节假日缺口导致数据不足
    return max(30, days + 10)


def _fetch_barchart_relative(symbol: str, start_date: date, end_date: date) -> List[ValuePoint]:
    client = barchart_api.Api()
    limit = _estimate_records(start_date, end_date)
    response = client.get_stock(symbol=symbol, max_records=limit)
    if response.status_code != 200:
        logger.error("Barchart API returned %s for %s", response.status_code, symbol)
        raise ValueError(f"Barchart API 请求失败 ({symbol})")
    raw_series = _parse_barchart_rows(response.text)
    filtered = [row for row in raw_series if start_date <= row[0] <= end_date]
    filtered.sort(key=lambda row: row[0])
    return _to_relative_points(filtered)


def get_market_breadth_series(
    session: Session, breadth_symbols: Sequence[str], range_key: str
) -> MarketBreadthResponse:
    if not breadth_symbols:
        raise ValueError("至少选择一个市场宽度指标")
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    benchmark_percent, benchmark_price = _load_benchmark(session, start, end)
    series_payload: List[RelativeSeries] = []
    errors: Dict[str, str] = {}
    for symbol in breadth_symbols:
        try:
            points = _fetch_barchart_relative(symbol, start, end)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        except ValueError as exc:
            errors[symbol] = str(exc)
            continue
        if points:
            series_payload.append(RelativeSeries(symbol=symbol, points=points))
    if not series_payload:
        detail = "; ".join(errors.values()) if errors else "无可用数据"
        raise ValueError(f"无法获取 Market Breadth 数据: {detail}")
    return MarketBreadthResponse(
        benchmark_percent=RelativeSeries(symbol="^NDX", points=benchmark_percent),
        benchmark_price=benchmark_price,
        series=series_payload,
    )
