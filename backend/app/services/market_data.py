from __future__ import annotations

from datetime import date
import logging
from typing import Dict, List, Sequence

from sqlalchemy import func
from sqlmodel import Session, select

from ..models.price import PriceRecord
from ..schemas.market import (
    DrawdownResponse,
    MarketSummary,
    OHLCVPoint,
    RelativeToResponse,
    SectorItem,
    SectorSummaryResponse,
    SeriesPayload,
    ValuePoint,
)
from .time_ranges import resolve_range_end, resolve_range_start
from .yahoo_client import fetch_and_store

logger = logging.getLogger(__name__)

SECTOR_LABELS: Dict[str, str] = {
    "XLC": "Comm Services",
    "XLY": "Consumer D",
    "XLP": "Consumer S",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "VNQ": "Real Estate",
    "XLK": "Tech",
    "XLU": "Utilities",
}


def ensure_history(session: Session, symbol: str, start: date, end: date) -> None:
    result = session.exec(
        select(func.min(PriceRecord.trade_date), func.max(PriceRecord.trade_date)).where(
            PriceRecord.symbol == symbol
        )
    ).first()
    if not result or result[0] is None or result[0] > start or result[1] is None or result[1] < end:
        fetch_and_store(session, symbol, start, end)


def to_points(records: Sequence[PriceRecord]) -> List[OHLCVPoint]:
    return [
        OHLCVPoint(
            time=record.trade_date,
            open=record.open,
            high=record.high,
            low=record.low,
            close=record.close,
            volume=record.volume,
        )
        for record in sorted(records, key=lambda r: r.trade_date)
    ]


def get_ohlcv_series(session: Session, symbol: str, range_key: str) -> SeriesPayload:
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    ensure_history(session, symbol, start, end)
    records = session.exec(
        select(PriceRecord)
        .where(PriceRecord.symbol == symbol)
        .where(PriceRecord.trade_date.between(start, end))
    ).all()
    return SeriesPayload(symbol=symbol, points=to_points(records))


def get_relative_performance(session: Session, symbols: List[str], range_key: str) -> List[Dict]:
    payload: List[Dict] = []
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    for symbol in symbols:
        ensure_history(session, symbol, start, end)
        records = session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == symbol)
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        ).all()
        if not records:
            continue
        first_close = next((r.close for r in records if r.close), None)
        if not first_close:
            continue
        series = []
        for record in records:
            if record.close is None:
                continue
            change_pct = ((record.close / first_close) - 1.0) * 100
            series.append({"time": record.trade_date, "value": change_pct})
        payload.append({"symbol": symbol, "points": series})
    return payload


def get_daily_performance(session: Session, symbols: List[str]) -> List[Dict]:
    results: List[Dict] = []
    for symbol in symbols:
        ensure_history(session, symbol, resolve_range_start("1M"), resolve_range_end())
        rows = _latest_two_records(session, symbol)
        if len(rows) < 2 or rows[0].close is None or rows[1].close is None:
            continue
        change_pct = ((rows[0].close - rows[1].close) / rows[1].close) * 100 if rows[1].close else 0
        results.append(
            {
                "symbol": symbol,
                "change_pct": change_pct,
                "latest_close": rows[0].close,
            }
        )
    return results


def get_drawdown_series(session: Session, symbol: str, range_key: str) -> DrawdownResponse:
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    ensure_history(session, symbol, start, end)
    records = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == symbol)
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    drawdown_points: List[ValuePoint] = []
    price_points: List[ValuePoint] = []
    peak: float | None = None
    current_drawdown = 0.0
    max_drawdown = 0.0
    for record in records:
        if record.close is None:
            continue
        price_points.append(ValuePoint(time=record.trade_date, value=record.close))
        peak = record.close if peak is None else max(peak, record.close)
        if not peak:
            continue
        drawdown_value = (record.close - peak) / peak * 100
        drawdown_value = min(drawdown_value, 0.0)
        current_drawdown = drawdown_value
        max_drawdown = min(max_drawdown, drawdown_value)
        drawdown_points.append(ValuePoint(time=record.trade_date, value=drawdown_value))
    return DrawdownResponse(
        symbol=symbol,
        drawdown=drawdown_points,
        price=price_points,
        current_drawdown=current_drawdown,
        max_drawdown=max_drawdown,
    )


def get_relative_to_series(
    session: Session, symbol: str, benchmark: str, range_key: str
) -> RelativeToResponse:
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    ensure_history(session, symbol, start, end)
    ensure_history(session, benchmark, start, end)

    symbol_rows = session.exec(
        select(PriceRecord)
        .where(PriceRecord.symbol == symbol)
        .where(PriceRecord.trade_date.between(start, end))
        .order_by(PriceRecord.trade_date)
    ).all()
    benchmark_rows = session.exec(
        select(PriceRecord)
        .where(PriceRecord.symbol == benchmark)
        .where(PriceRecord.trade_date.between(start, end))
        .order_by(PriceRecord.trade_date)
    ).all()
    benchmark_map = {row.trade_date: row.close for row in benchmark_rows if row.close}

    ratio_points: List[ValuePoint] = []
    values: List[float] = []
    for row in symbol_rows:
        if not row.close:
            continue
        bench_close = benchmark_map.get(row.trade_date)
        if not bench_close:
            continue
        ratio = (row.close / bench_close) * 100
        values.append(ratio)
        ratio_points.append(ValuePoint(time=row.trade_date, value=ratio))

    moving_average: List[ValuePoint] = []
    window = 30
    for index, value in enumerate(values):
        if index + 1 < window:
            continue
        window_slice = values[index + 1 - window : index + 1]
        avg = sum(window_slice) / window
        moving_average.append(ValuePoint(time=ratio_points[index].time, value=avg))

    return RelativeToResponse(
        symbol=symbol,
        benchmark=benchmark,
        ratio=ratio_points,
        moving_average=moving_average,
    )


def _latest_two_records(session: Session, symbol: str) -> List[PriceRecord]:
    return (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == symbol)
            .order_by(PriceRecord.trade_date.desc())
            .limit(2)
        )
        .unique()
        .all()
    )


def get_market_summary(session: Session, market: str) -> MarketSummary:
    symbol = "SPY" if market.lower() == "sp500" else "QQQ"
    ensure_history(session, symbol, resolve_range_start("1Y"), resolve_range_end())
    rows = _latest_two_records(session, symbol)
    if len(rows) < 2 or rows[0].close is None or rows[1].close is None:
        raise ValueError("Insufficient data for market summary")
    latest, previous = rows
    day_change = latest.close - previous.close
    day_change_pct = (day_change / previous.close) * 100 if previous.close else 0

    vix_symbol = "^VIX"
    ensure_history(session, vix_symbol, resolve_range_start("1Y"), resolve_range_end())
    vix_rows = _latest_two_records(session, vix_symbol)
    if len(vix_rows) < 2 or vix_rows[0].close is None or vix_rows[1].close is None:
        raise ValueError("Insufficient data for VIX summary")
    vix_change = (
        ((vix_rows[0].close - vix_rows[1].close) / vix_rows[1].close) * 100
        if vix_rows[1].close
        else 0
    )

    return MarketSummary(
        market=market.upper(),
        date=rows[0].trade_date,
        index_value=rows[0].close,
        day_change=day_change,
        day_change_pct=day_change_pct,
        vix_value=vix_rows[0].close,
        vix_change_pct=vix_change,
    )


def get_sector_summary(session: Session) -> SectorSummaryResponse:
    items: List[SectorItem] = []
    for symbol, label in SECTOR_LABELS.items():
        ensure_history(session, symbol, resolve_range_start("1Y"), resolve_range_end())
        rows = _latest_two_records(session, symbol)
        if len(rows) < 2 or rows[0].close is None or rows[1].close is None:
            continue
        change_pct = ((rows[0].close - rows[1].close) / rows[1].close) * 100 if rows[1].close else 0
        volume_millions = (rows[0].volume or 0) / 1_000_000
        volume_samples = session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == symbol)
            .order_by(PriceRecord.trade_date.desc())
            .limit(60)
        ).all()
        filtered = [row.volume for row in volume_samples if row.volume]
        avg = (sum(filtered) / len(filtered)) if filtered else 0
        percent_of_avg = ((rows[0].volume or 0) / avg * 100) if avg else 0
        items.append(
            SectorItem(
                name=label,
                symbol=symbol,
                change_pct=change_pct,
                volume_millions=volume_millions,
                percent_of_avg=percent_of_avg,
            )
        )
    return SectorSummaryResponse(sectors=items)
