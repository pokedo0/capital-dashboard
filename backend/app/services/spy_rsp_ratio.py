"""SPY/RSP ratio calculation service.

This module calculates the ratio of SPY (S&P 500 ETF) to RSP (equal-weight S&P 500 ETF),
which indicates market breadth concentration. A high ratio (above 3.5) suggests that
market gains are driven by a few large-cap stocks rather than broad participation.
"""

from __future__ import annotations

import logging
from typing import List

from sqlmodel import Session, select

from ..models.price import PriceRecord
from ..schemas.market import SpyRspRatioResponse, ValuePoint
from .market_data import ensure_history
from .time_ranges import resolve_range_end, resolve_range_start

logger = logging.getLogger(__name__)


def get_spy_rsp_ratio(session: Session, range_key: str) -> SpyRspRatioResponse:
    """Calculate SPY/RSP ratio and return with MAGS ETF price series."""
    start = resolve_range_start(range_key)
    end = resolve_range_end()

    # Ensure we have data for SPY, RSP, and MAGS
    for symbol in ["SPY", "RSP", "MAGS"]:
        ensure_history(session, symbol, start, end)

    # Fetch SPY prices
    spy_rows = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == "SPY")
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    spy_map = {row.trade_date: row.close for row in spy_rows if row.close is not None}

    # Fetch RSP prices
    rsp_rows = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == "RSP")
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    rsp_map = {row.trade_date: row.close for row in rsp_rows if row.close is not None}

    # Fetch MAGS prices
    mags_rows = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == "MAGS")
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    mags_points = [
        ValuePoint(time=row.trade_date, value=row.close)
        for row in mags_rows
        if row.close is not None
    ]

    # Calculate SPY/RSP ratio for dates where both have data
    ratio_points: List[ValuePoint] = []
    common_dates = sorted(set(spy_map.keys()) & set(rsp_map.keys()))
    for trade_date in common_dates:
        spy_price = spy_map[trade_date]
        rsp_price = rsp_map[trade_date]
        if rsp_price > 0:
            ratio = spy_price / rsp_price
            ratio_points.append(ValuePoint(time=trade_date, value=ratio))

    if not ratio_points:
        raise ValueError("无法计算 SPY/RSP 比率，数据不足")

    return SpyRspRatioResponse(ratio=ratio_points, mags=mags_points)
