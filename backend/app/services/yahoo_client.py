from __future__ import annotations

from datetime import date, timedelta
import logging
import os
from typing import List, Optional

import pandas as pd

# 强制关闭 yfinance 的 curl_cffi，避免环境中 curl/openssl 导致 TLS 异常
os.environ.setdefault("YF_NO_CURL", "1")
os.environ.setdefault("YF_ENABLE_CURL", "0")
import yfinance as yf  # noqa: E402
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
        auto_adjust=True,
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


def _safe_float(value: Optional[float]) -> Optional[float]:
    return float(value) if value is not None and pd.notna(value) else None


def fetch_and_store(session: Session, symbol: str, start: date, end: date) -> None:
    try:
        df = _download(symbol, start, end)
    except Exception as exc:  # pragma: no cover - network/runtime errors
        logger.warning("Failed to download %s: %s", symbol, exc)
        return
    if df.empty:
        logger.warning("Yahoo returned empty frame for %s (%s -> %s)", symbol, start, end)
        return

    for index, row in df.iterrows():
        trade_date = index.date()
        existing = session.get(PriceRecord, (symbol, trade_date))
        if existing:
            existing.open = _safe_float(row.get("Open"))
            existing.high = _safe_float(row.get("High"))
            existing.low = _safe_float(row.get("Low"))
            existing.close = _safe_float(row.get("Close"))
            existing.volume = _safe_float(row.get("Volume"))
        else:
            new_record = PriceRecord(
                symbol=symbol,
                trade_date=trade_date,
                open=_safe_float(row.get("Open")),
                high=_safe_float(row.get("High")),
                low=_safe_float(row.get("Low")),
                close=_safe_float(row.get("Close")),
                volume=_safe_float(row.get("Volume")),
            )
            session.add(new_record)

    session.commit()