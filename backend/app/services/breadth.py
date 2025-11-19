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
    if not series:
        return []
    first_value = next((value for _, value in series if value is not None and value != 0), None)
    if first_value is None:
        return []
    points: List[ValuePoint] = []
    for entry_date, value in series:
        change_pct = ((value / first_value) - 1.0) * 100
        points.append(ValuePoint(time=entry_date, value=change_pct))
    return points


def _load_benchmark(session: Session, start_date: date, end_date: date) -> List[ValuePoint]:
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
    for record in records:
        if record.close is None:
            continue
        pairs.append((record.trade_date, record.close))
    return _to_relative_points(pairs)


def _fetch_barchart_relative(symbol: str, start_date: date, end_date: date) -> List[ValuePoint]:
    client = barchart_api.Api()
    response = client.get_stock(symbol=symbol, start_date=start_date, end_date=end_date, order="asc")
    if response.status_code != 200:
        logger.error("Barchart API returned %s for %s", response.status_code, symbol)
        raise ValueError(f"Barchart API 请求失败 ({symbol})")
    raw_series = _parse_barchart_rows(response.text)
    filtered = [row for row in raw_series if start_date <= row[0] <= end_date]
    return _to_relative_points(filtered)


def get_market_breadth_series(
    session: Session, breadth_symbols: Sequence[str], range_key: str
) -> MarketBreadthResponse:
    if not breadth_symbols:
        raise ValueError("至少选择一个市场宽度指标")
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    benchmark_points = _load_benchmark(session, start, end)
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
        benchmark=RelativeSeries(symbol="^NDX", points=benchmark_points),
        series=series_payload,
    )
