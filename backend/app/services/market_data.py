from __future__ import annotations

from datetime import date, datetime
import json
import logging
import os
from typing import Dict, List, Sequence, Tuple
from urllib.error import URLError
from urllib.request import urlopen, Request

import pandas as pd
import requests

# 强制关闭 yfinance 的 curl_cffi，避免环境中 curl/openssl 导致 TLS 异常
os.environ.setdefault("YF_NO_CURL", "1")
os.environ.setdefault("YF_ENABLE_CURL", "0")
import yfinance as yf  # noqa: E402
from sqlalchemy import func
from sqlmodel import Session, select

from ..models.price import PriceRecord
from ..core.config import get_settings
from ..utils.cache import TTLCache
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

settings = get_settings()

logger = logging.getLogger(__name__)

# 复用 10 分钟行情缓存，避免在多个接口中重复查询相同区间的价格序列
price_series_cache: TTLCache[List[PriceRecord]] = TTLCache(settings.cache_ttl_seconds)

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
ALT_SP500_CONSTITUENTS_URL = "https://raw.githubusercontent.com/pokedo0/index-constituents/main/docs/constituents-sp500.csv"
ALT_NASDAQ100_CONSTITUENTS_URL = "https://raw.githubusercontent.com/pokedo0/index-constituents/main/docs/constituents-nasdaq100.csv"


def ensure_history(session: Session, symbol: str, start: date, end: date) -> None:
    # 1. 快速检查（只读）
    result = session.exec(
        select(func.min(PriceRecord.trade_date), func.max(PriceRecord.trade_date)).where(
            PriceRecord.symbol == symbol
        )
    ).first()
    
    # 2. 如果数据缺失，则启动一个全新的独立会话进行写入
    if not result or result[0] is None or result[0] > start or result[1] is None or result[1] < end:
        # 使用独立的 Engine 连接创建临时的 Session，确保事务隔离
        # 避免在此处复用传入的 `session`，防止 SQLite 锁定或事务状态污染
        from sqlmodel import Session as NewSession
        from ..db import engine
        
        with NewSession(engine) as write_session:
            fetch_and_store(write_session, symbol, start, end)
            # fetch_and_store 内部负责 commit，这里无需再次操作


def _load_price_records(session: Session, symbol: str, start: date, end: date) -> List[PriceRecord]:
    normalized = symbol.upper()
    key = (normalized, start, end)

    def _creator() -> List[PriceRecord]:
        ensure_history(session, normalized, start, end)
        return (
            session.exec(
                select(PriceRecord)
                .where(PriceRecord.symbol == normalized)
                .where(PriceRecord.trade_date.between(start, end))
                .order_by(PriceRecord.trade_date)
            )
            .unique()
            .all()
        )

    return price_series_cache.get_or_set(key, _creator)


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
    records = _load_price_records(session, symbol, start, end)
    return SeriesPayload(symbol=symbol, points=to_points(records))


def get_relative_performance(session: Session, symbols: List[str], range_key: str) -> List[Dict]:
    payload: List[Dict] = []
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    for symbol in symbols:
        records = _load_price_records(session, symbol, start, end)
        if not records:
            continue
        first_close = next((r.close for r in records if r.close), None)
        if not first_close or first_close == 0:
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
    records = _load_price_records(session, symbol, start, end)
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
    symbol_rows = _load_price_records(session, symbol, start, end)
    benchmark_rows = _load_price_records(session, benchmark, start, end)
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


def _parse_pct(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return None
    text = str(value).strip().replace("(", "").replace(")", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _fetch_constituents_changes(url: str) -> Tuple[float | None, float | None]:
    """
    读取成分股 CSV，返回 (advancers_pct, decliners_pct)，涨跌判断基于列 `Chg`（绝对变化）。
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network issues
        logger.warning("Failed to fetch constituents CSV %s: %s", url, exc)
        return None, None

    try:
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to parse constituents CSV %s: %s", url, exc)
        return None, None

    if "Symbol" not in df.columns or "Chg" not in df.columns:
        logger.warning("Constituents CSV missing required columns")
        return None, None

    total = len(df)
    if total == 0:
        return None, None

    advancers = decliners = flats = 0
    for _, row in df.iterrows():
        change_val = _parse_pct(row.get("Chg"))
        if change_val is None:
            continue
        if change_val > 0:
            advancers += 1
        elif change_val < 0:
            decliners += 1
        else:
            flats += 1

    tracked = advancers + decliners + flats
    adv_pct = (advancers / tracked * 100) if tracked else None
    dec_pct = (decliners / tracked * 100) if tracked else None

    return adv_pct, dec_pct


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
    benchmark_symbol = "^GSPC"
    ensure_history(session, benchmark_symbol, start, end)
    benchmark_records = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == benchmark_symbol)
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    benchmark_points = [
        ValuePoint(time=record.trade_date, value=record.close)
        for record in benchmark_records
        if record.close is not None
    ]
    return FearGreedResponse(index=index_points, spy=benchmark_points)


def _load_constituents(url: str, label: str) -> List[str]:
    logger.info("Loading %s constituents from %s", label, url)
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as response:
            df = pd.read_csv(response)
    except Exception as exc:  # pragma: no cover - network/runtime issues
        logger.warning("Failed to load %s constituents: %s", label, exc)
        return []
    if "Symbol" not in df.columns:
        logger.warning("%s constituents CSV missing Symbol column", label)
        return []
    normalized: List[str] = []
    for raw in df["Symbol"].tolist():
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        normalized.append(symbol.replace(".", "-"))
    unique = list(dict.fromkeys(normalized))
    logger.info("Loaded %d %s tickers for breadth calculation", len(unique), label)
    return unique


def _download_prices(symbols: List[str], label: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    logger.info("Downloading %s prices (%d symbols)", label, len(symbols))
    try:
        df = yf.download(
            symbols,
            period="5d",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=False,
            actions=False,
        )
    except Exception as exc:  # pragma: no cover - network/runtime issues
        logger.warning("Failed to download %s prices: %s", label, exc)
        return pd.DataFrame()
    if df.empty:
        logger.warning("%s price download returned empty frame", label)
        return pd.DataFrame()
    if not isinstance(df.columns, pd.MultiIndex):
        df = pd.concat({symbols[0]: df}, axis=1)
    logger.info("Completed downloading %s prices", label)
    return df


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


def _calculate_breadth(price_frame: pd.DataFrame, symbols: List[str]) -> Tuple[float | None, float | None]:
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
        "Breadth summary: up=%d down=%d flat=%d missing=%d (tracked=%d)",
        up,
        down,
        flat,
        missing,
        len(symbols),
    )
    if total == 0:
        return None, None
    return (up / total * 100, down / total * 100)


def _latest_market_rows(session: Session, symbol: str) -> List[PriceRecord] | None:
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
        logger.info("Calculating S&P 500 advance/decline percentages from CSV")
        advancers_pct, decliners_pct = _fetch_constituents_changes(ALT_SP500_CONSTITUENTS_URL)
    elif market_key == "nasdaq":
        logger.info("Calculating Nasdaq 100 advance/decline percentages from CSV")
        advancers_pct, decliners_pct = _fetch_constituents_changes(ALT_NASDAQ100_CONSTITUENTS_URL)

    ensure_history(session, symbol, resolve_range_start("1Y"), resolve_range_end())
    rows = _latest_market_rows(session, symbol)
    if not rows:
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
