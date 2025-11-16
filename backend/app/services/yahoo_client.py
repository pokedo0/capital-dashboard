from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List

import pandas as pd
import yfinance as yf
from sqlmodel import Session

from ..models.price import PriceRecord


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
    )
    return data


def fetch_and_store(session: Session, symbol: str, start: date, end: date) -> List[PriceRecord]:
    df = _download(symbol, start, end)
    if df.empty:
        return []

    records: List[PriceRecord] = []
    for index, row in df.iterrows():
        trade_date = index.date()
        record = PriceRecord(
            symbol=symbol,
            trade_date=trade_date,
            open=float(row["Open"]) if not pd.isna(row["Open"]) else None,
            high=float(row["High"]) if not pd.isna(row["High"]) else None,
            low=float(row["Low"]) if not pd.isna(row["Low"]) else None,
            close=float(row["Close"]) if not pd.isna(row["Close"]) else None,
            volume=float(row["Volume"]) if not pd.isna(row["Volume"]) else None,
        )
        session.merge(record)
        records.append(record)

    session.commit()
    return records
