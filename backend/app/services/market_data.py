from __future__ import annotations

from datetime import date, datetime
import json
import logging
import os
from typing import Dict, List, Sequence, Tuple
from urllib.error import URLError
from urllib.request import urlopen, Request

import pandas as pd

# 强制关闭 yfinance 的 curl_cffi，避免环境中 curl/openssl 导致 TLS 异常
os.environ.setdefault("YF_NO_CURL", "1")
os.environ.setdefault("YF_ENABLE_CURL", "0")
import yfinance as yf  # noqa: E402
from sqlalchemy import func
from sqlmodel import Session, select

from ..models.price import PriceRecord
from ..schemas.market import (
    DrawdownResponse,
    FearGreedResponse,
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

FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
SP500_CONSTITUENTS_URL = (
    "https://jcoffi.github.io/index-constituents/constituents-sp500.csv"
)
SP500_CHUNK_SIZE = 500


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
    normalized_values: List[float] = []
    base_ratio: float | None = None
    for row in symbol_rows:
        if row.close is None:
            continue
        bench_close = benchmark_map.get(row.trade_date)
        if bench_close is None or bench_close == 0:
            continue
        raw_ratio = row.close / bench_close
        if base_ratio is None:
            base_ratio = raw_ratio
        normalized = (raw_ratio / base_ratio) * 100
        normalized_values.append(normalized)
        ratio_points.append(ValuePoint(time=row.trade_date, value=normalized))

    moving_average: List[ValuePoint] = []
    window = 50
    for index, value in enumerate(normalized_values):
        if index + 1 < window:
            continue
        window_slice = normalized_values[index + 1 - window : index + 1]
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


def _fetch_fear_greed_history() -> List[ValuePoint]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
        "Origin": "https://edition.cnn.com",
    }
    try:
        request = Request(FEAR_GREED_URL, headers=headers)
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except URLError as exc:  # pragma: no cover - network error handling
        logger.error("Failed to fetch Fear & Greed Index data: %s", exc)
        raise ValueError("Unable to fetch Fear & Greed Index data") from exc
    except Exception as exc:  # pragma: no cover - unexpected issues
        logger.error("Unexpected error fetching Fear & Greed Index data: %s", exc)
        raise ValueError("Unable to fetch Fear & Greed Index data") from exc
    historical_block = payload.get("fear_and_greed_historical", {})
    historical = historical_block.get("data", []) if isinstance(historical_block, dict) else historical_block
    points: List[ValuePoint] = []
    for item in historical:
        timestamp = item.get("x")
        value = item.get("y")
        if timestamp is None or value is None:
            continue
        try:
            time_value = datetime.utcfromtimestamp(timestamp / 1000).date()
        except Exception:  # pragma: no cover - skip bad rows
            continue
        points.append(ValuePoint(time=time_value, value=float(value)))
    return points


def get_fear_greed_comparison(session: Session, range_key: str) -> FearGreedResponse:
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    index_points = [
        point for point in _fetch_fear_greed_history() if start <= point.time <= end
    ]
    ensure_history(session, "SPY", start, end)
    spy_records = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == "SPY")
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    spy_points = [
        ValuePoint(time=record.trade_date, value=record.close)
        for record in spy_records
        if record.close is not None
    ]
    return FearGreedResponse(index=index_points, spy=spy_points)


def _load_sp500_constituents() -> List[str]:
    logger.info("Loading S&P 500 constituents from %s", SP500_CONSTITUENTS_URL)
    try:
        request = Request(SP500_CONSTITUENTS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as response:
            df = pd.read_csv(response)
    except Exception as exc:  # pragma: no cover - network/runtime issues
        logger.warning("Failed to load S&P 500 constituents: %s", exc)
        return []
    if "Symbol" not in df.columns:
        logger.warning("S&P 500 constituents CSV missing Symbol column")
        return []
    normalized: List[str] = []
    for raw in df["Symbol"].tolist():
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        normalized.append(symbol.replace(".", "-"))
    unique = list(dict.fromkeys(normalized))
    logger.info("Loaded %d S&P 500 tickers for breadth calculation", len(unique))
    return unique


def _chunked(items: List[str], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _download_sp500_prices(symbols: List[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    frames: List[pd.DataFrame] = []
    total_chunks = (len(symbols) + SP500_CHUNK_SIZE - 1) // SP500_CHUNK_SIZE
    for index, chunk in enumerate(_chunked(symbols, SP500_CHUNK_SIZE), start=1):
        logger.info(
            "Downloading S&P 500 prices chunk %d/%d (%d symbols)",
            index,
            total_chunks,
            len(chunk),
        )
        try:
            df = yf.download(
                chunk,
                period="5d",
                group_by="ticker",
                progress=False,
                threads=True,
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:  # pragma: no cover - network/runtime issues
            logger.warning("Chunk %d download failed: %s", index, exc)
            continue
        if df.empty:
            logger.warning("Chunk %d/%d returned empty price frame", index, total_chunks)
            continue
        if not isinstance(df.columns, pd.MultiIndex):
            df = pd.concat({chunk[0]: df}, axis=1)
        frames.append(df)
    if not frames:
        logger.warning("No price data downloaded for S&P 500 constituents")
        return pd.DataFrame()
    merged = pd.concat(frames, axis=1)
    logger.info("Completed downloading prices for %d symbols", len(symbols))
    return merged


def _extract_closes(price_frame: pd.DataFrame, symbol: str) -> pd.Series | None:
    if price_frame.empty:
        return None
    try:
        if isinstance(price_frame.columns, pd.MultiIndex):
            if symbol not in price_frame.columns.get_level_values(0):
                return None
            closes = price_frame[symbol].get("Close")
        else:
            closes = price_frame.get("Close")
    except Exception:
        return None
    if closes is None:
        return None
    return closes.dropna()


def _calculate_sp500_breadth(price_frame: pd.DataFrame, symbols: List[str]) -> Tuple[float | None, float | None]:
    up = down = flat = missing = 0
    for symbol in symbols:
        closes = _extract_closes(price_frame, symbol)
        if closes is None or len(closes) < 2:
            missing += 1
            continue
        latest = closes.iloc[-1]
        previous = closes.iloc[-2]
        if pd.isna(latest) or pd.isna(previous) or previous == 0:
            missing += 1
            continue
        change_pct = ((latest - previous) / previous) * 100
        if change_pct > 0:
            up += 1
        elif change_pct < 0:
            down += 1
        else:
            flat += 1
    total = up + down + flat
    logger.info(
        "S&P 500 breadth summary: up=%d down=%d flat=%d missing=%d (tracked=%d)",
        up,
        down,
        flat,
        missing,
        len(symbols),
    )
    if total == 0:
        return None, None
    return (up / total * 100, down / total * 100)


def _sp500_advance_decline() -> Tuple[float | None, float | None]:
    symbols = _load_sp500_constituents()
    if not symbols:
        return None, None
    price_frame = _download_sp500_prices(symbols)
    if price_frame.empty:
        return None, None
    return _calculate_sp500_breadth(price_frame, symbols)


def _latest_market_rows(session: Session, symbol: str) -> List[PriceRecord] | None:
    ensure_history(session, symbol, resolve_range_start("1Y"), resolve_range_end())
    rows = _latest_two_records(session, symbol)
    if len(rows) < 2 or rows[0].close is None or rows[1].close is None:
        return None
    return rows


def get_market_summary(session: Session, market: str) -> MarketSummary:
    market_key = market.lower()
    symbol_map = {"sp500": ["^GSPC", "SPY"], "nasdaq": ["^NDX", "QQQ"]}
    candidates = symbol_map.get(market_key, ["QQQ"])
    rows: List[PriceRecord] | None = None
    symbol = candidates[0]
    for candidate in candidates:
        rows = _latest_market_rows(session, candidate)
        if rows:
            symbol = candidate
            break
    if not rows:
        raise ValueError("Insufficient data for market summary")
    advancers_pct: float | None = None
    decliners_pct: float | None = None
    if market_key == "sp500":
        logger.info("Calculating S&P 500 advance/decline percentages")
        advancers_pct, decliners_pct = _sp500_advance_decline()
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
        advancers_pct=advancers_pct,
        decliners_pct=decliners_pct,
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
