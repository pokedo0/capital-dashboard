from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import List

import pandas as pd
import yfinance as yf
from sqlmodel import Session

from ..models.price import PriceRecord

logger = logging.getLogger(__name__)


def _download(symbol: str, start: date, end: date) -> pd.DataFrame:
    # yfinance end is exclusive, so extend by one day to capture final date
    yf_end = end + timedelta(days=1)
    data = yf.download(
        symbol,
        start=start.isoformat(),
        end=yf_end.isoformat(),
        progress=False,
        auto_adjust=False,
        actions=False,
        group_by="column",
        threads=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        try:
            data = data.xs(symbol, axis=1, level=-1)
        except KeyError:
            data = data.droplevel(0, axis=1)
    data.columns = [col.capitalize() for col in data.columns]
    return data


def fetch_and_store(session: Session, symbol: str, start: date, end: date) -> List[PriceRecord]:
    try:
        df = _download(symbol, start, end)
    except Exception as exc:  # pragma: no cover - network/runtime errors
        logger.warning("Failed to download %s: %s", symbol, exc)
        return []
    if df.empty:
        return []

    records: List[PriceRecord] = []
    for index, row in df.iterrows():
        trade_date = index.date()
        record = PriceRecord(
            symbol=symbol,
            trade_date=trade_date,
            open=float(row.get("Open")) if pd.notna(row.get("Open")) else None,
            high=float(row.get("High")) if pd.notna(row.get("High")) else None,
            low=float(row.get("Low")) if pd.notna(row.get("Low")) else None,
            close=float(row.get("Close")) if pd.notna(row.get("Close")) else None,
            volume=float(row.get("Volume")) if pd.notna(row.get("Volume")) else None,
        )
        session.merge(record)
        records.append(record)

    session.commit()
    return records
