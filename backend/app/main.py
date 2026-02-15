from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import logging
from logging.config import dictConfig
import threading
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .core.config import get_settings
from .db import get_session, init_db, session_scope
from .schemas.market import (
    DrawdownResponse,
    FearGreedResponse,
    ForwardPeResponse,
    MarketBreadthResponse,
    MarketSummary,
    RelativeToResponse,
    SectorSummaryResponse,
    SeriesPayload,
    SpyRspRatioResponse,
)
from .services.market_data import (
    get_daily_performance,
    get_drawdown_series,
    get_fear_greed_comparison,
    get_market_summary,
    get_ohlcv_series,
    get_relative_to_series,
    get_relative_performance,
    get_sector_summary,
    price_series_cache,
)
from .services.breadth import get_market_breadth_series
from .services.forward_pe import get_forward_pe_comparison
from .services.spy_rsp_ratio import get_spy_rsp_ratio
from .services.realtime import get_realtime_market_summary, get_realtime_sector_summary
from .services.time_ranges import RANGE_TO_DAYS
from .services.yahoo_client import fetch_and_store
from .services.leveraged_etf import (
    fetch_and_store_leveraged_etf_data,
    calculate_leveraged_etf_prices,
)
from .schemas.leveraged_etf import LeveragedETFResponse
from .utils.cache import TTLCache

# Realtime cache TTL: 5 minutes (300 seconds)
REALTIME_CACHE_TTL = 300

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        }
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "INFO"},
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}

dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(title=settings.app_name)
scheduler = AsyncIOScheduler(timezone=settings.timezone)

ohlcv_cache: TTLCache[SeriesPayload] = TTLCache(settings.cache_ttl_seconds)
relative_cache: TTLCache[List[dict]] = TTLCache(settings.cache_ttl_seconds)
daily_cache: TTLCache[List[dict]] = TTLCache(settings.cache_ttl_seconds)
market_cache: TTLCache[MarketSummary] = TTLCache(settings.cache_ttl_seconds)
sector_cache: TTLCache[SectorSummaryResponse] = TTLCache(settings.cache_ttl_seconds)
drawdown_cache: TTLCache[DrawdownResponse] = TTLCache(settings.cache_ttl_seconds)
relative_to_cache: TTLCache[RelativeToResponse] = TTLCache(settings.cache_ttl_seconds)
fear_greed_cache: TTLCache[FearGreedResponse] = TTLCache(settings.cache_ttl_seconds)
breadth_cache: TTLCache[MarketBreadthResponse] = TTLCache(settings.cache_ttl_seconds)
forward_pe_cache: TTLCache[ForwardPeResponse] = TTLCache(settings.cache_ttl_seconds)
spy_rsp_cache: TTLCache[SpyRspRatioResponse] = TTLCache(settings.cache_ttl_seconds)

# Realtime caches with 5-minute TTL
realtime_market_cache: TTLCache[MarketSummary] = TTLCache(REALTIME_CACHE_TTL)
realtime_sector_cache: TTLCache[SectorSummaryResponse] = TTLCache(REALTIME_CACHE_TTL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _refresh_one_symbol(symbol: str, start: date, end: date) -> None:
    """Download and store history for a single symbol in its own session."""
    try:
        with session_scope() as session:
            fetch_and_store(session, symbol, start, end)
    except Exception as exc:  # pragma: no cover
        logger.warning("Startup download failed for %s: %s", symbol, exc)


def _refresh_history(symbols: List[str], years: int = 5, max_workers: int = 6) -> None:
    start = date.today() - timedelta(days=365 * years)
    end = date.today()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_refresh_one_symbol, symbol, start, end): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                future.result()
            except Exception as exc:  # pragma: no cover
                logger.warning("Startup download error for %s: %s", symbol, exc)


def clear_all_caches(source: str = "unknown") -> None:
    logger.info("Clearing caches (source=%s)", source)
    ohlcv_cache.clear()
    relative_cache.clear()
    daily_cache.clear()
    market_cache.clear()
    sector_cache.clear()
    drawdown_cache.clear()
    relative_to_cache.clear()
    fear_greed_cache.clear()
    breadth_cache.clear()
    forward_pe_cache.clear()
    spy_rsp_cache.clear()
    price_series_cache.clear()
    realtime_market_cache.clear()
    realtime_sector_cache.clear()


def daily_refresh_job() -> None:
    refresh_symbols = list(
        dict.fromkeys(
            settings.yahoo_batch_symbols + settings.mag7_symbols + settings.multi_asset_symbols
        )
    )
    start = date.today() - timedelta(days=10)
    end = date.today()
    with session_scope() as session:
        for symbol in refresh_symbols:
            fetch_and_store(session, symbol, start, end)
    clear_all_caches(source="scheduler")


# Track whether initial data loading has finished
_startup_ready = threading.Event()


def _background_startup() -> None:
    """Heavy startup work: download history + load ETF CSV.  Runs in a daemon thread."""
    try:
        all_symbols = list(
            dict.fromkeys(
                settings.yahoo_batch_symbols
                + settings.mag7_symbols
                + settings.multi_asset_symbols
                + ["SPY", "QQQ"]
            )
        )
        _refresh_history(all_symbols)
        # Load leveraged ETF data from CSV
        with session_scope() as session:
            fetch_and_store_leveraged_etf_data(session)
        logger.info("Background startup finished – all data loaded.")
    except Exception as exc:  # pragma: no cover
        logger.error("Background startup error: %s", exc)
    finally:
        _startup_ready.set()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    # Kick off heavy data loading in a daemon thread so the server is
    # immediately responsive.  The API endpoints can serve data as soon
    # as their own caches are warm.
    t = threading.Thread(target=_background_startup, daemon=True, name="startup-loader")
    t.start()
    # 美东时间 16:15（刚收盘后）跑一次增量刷新
    scheduler.add_job(daily_refresh_job, "cron", day_of_week="mon-fri", hour=16, minute=15)
    # 美东时间 18:00（夜盘/盘后时段开始后）再跑一次，覆盖盘后数据
    scheduler.add_job(daily_refresh_job, "cron", day_of_week="mon-fri", hour=18, minute=15)
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown()


@app.get("/api/health")
def api_health() -> dict:
    """Lightweight health-check that also reports startup readiness."""
    return {"status": "ok", "ready": _startup_ready.is_set()}


@app.get("/api/time-ranges")
def list_time_ranges() -> List[str]:
    return list(RANGE_TO_DAYS.keys())


@app.get("/api/ohlcv", response_model=SeriesPayload)
def api_get_ohlcv(
    symbol: str = Query(..., description="Ticker symbol, e.g. SPY"),
    range_key: str = Query("1Y", alias="range"),
    session: Session = Depends(get_session),
) -> SeriesPayload:
    key = (symbol, range_key.upper())
    try:
        return ohlcv_cache.get_or_set(key, lambda: get_ohlcv_series(session, symbol, range_key))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/performance/relative")
def api_relative_performance(
    symbols: str = Query(..., description="Comma separated symbols"),
    range_key: str = Query("1M", alias="range"),
    session: Session = Depends(get_session),
):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="symbols parameter required")

    key = ("relative", ",".join(symbol_list), range_key.upper())
    try:
        return relative_cache.get_or_set(
            key, lambda: get_relative_performance(session, symbol_list, range_key)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/performance/daily")
def api_daily_performance(
    symbols: str = Query(..., description="Comma separated symbols"),
    session: Session = Depends(get_session),
):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="symbols parameter required")
    key = ("daily", ",".join(symbol_list))
    return daily_cache.get_or_set(key, lambda: get_daily_performance(session, symbol_list))


@app.get("/api/performance/drawdown", response_model=DrawdownResponse)
def api_drawdown(
    symbol: str = Query(..., description="Ticker symbol"),
    range_key: str = Query("1Y", alias="range"),
    session: Session = Depends(get_session),
) -> DrawdownResponse:
    cache_key = (symbol.upper(), range_key.upper())
    try:
        return drawdown_cache.get_or_set(
            cache_key, lambda: get_drawdown_series(session, symbol.upper(), range_key)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/performance/relative-to", response_model=RelativeToResponse)
def api_relative_to(
    symbol: str = Query(..., description="Primary ticker"),
    benchmark: str = Query(..., description="Benchmark ticker"),
    range_key: str = Query("1Y", alias="range"),
    session: Session = Depends(get_session),
) -> RelativeToResponse:
    cache_key = (symbol.upper(), benchmark.upper(), range_key.upper())
    try:
        return relative_to_cache.get_or_set(
            cache_key,
            lambda: get_relative_to_series(session, symbol.upper(), benchmark.upper(), range_key),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/market/summary", response_model=MarketSummary)
def api_market_summary(
    market: str = Query("sp500"), session: Session = Depends(get_session)
) -> MarketSummary:
    key = market.lower()
    try:
        return market_cache.get_or_set(key, lambda: get_market_summary(session, market))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/sectors/summary", response_model=SectorSummaryResponse)
def api_sector_summary(session: Session = Depends(get_session)) -> SectorSummaryResponse:
    return sector_cache.get_or_set("sectors", lambda: get_sector_summary(session))


@app.get("/api/market/fear-greed", response_model=FearGreedResponse)
def api_fear_greed(
    range_key: str = Query("1Y", alias="range"), session: Session = Depends(get_session)
) -> FearGreedResponse:
    key = range_key.upper()
    try:
        return fear_greed_cache.get_or_set(key, lambda: get_fear_greed_comparison(session, range_key))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/market/breadth", response_model=MarketBreadthResponse)
def api_market_breadth(
    symbols: str = Query("$NDTW", description="Comma separated Barchart breadth symbols"),
    range_key: str = Query("1M", alias="range"),
    benchmark: str = Query("^NDX", description="Benchmark symbol for comparison"),
    session: Session = Depends(get_session),
) -> MarketBreadthResponse:
    requested = [token.strip() for token in symbols.split(",") if token.strip()]
    normalized = []
    for token in requested:
        symbol = token.upper()
        if symbol and not symbol.startswith("$"):
            symbol = f"${symbol}"
        if symbol:
            normalized.append(symbol)
    if not normalized:
        raise HTTPException(status_code=400, detail="symbols parameter required")
    benchmark_symbol = benchmark.strip().upper()
    if not benchmark_symbol:
        raise HTTPException(status_code=400, detail="benchmark parameter required")
    cache_key = ("breadth", ",".join(normalized), range_key.upper(), benchmark_symbol)
    try:
        return breadth_cache.get_or_set(
            cache_key,
            lambda: get_market_breadth_series(session, normalized, range_key, benchmark_symbol),
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/market/forward-pe", response_model=ForwardPeResponse)
def api_forward_pe(
    range_key: str = Query("1Y", alias="range"), session: Session = Depends(get_session)
) -> ForwardPeResponse:
    cache_key = range_key.upper()
    try:
        return forward_pe_cache.get_or_set(
            cache_key, lambda: get_forward_pe_comparison(session, range_key)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/market/spy-rsp-ratio", response_model=SpyRspRatioResponse)
def api_spy_rsp_ratio(
    range_key: str = Query("1Y", alias="range"), session: Session = Depends(get_session)
) -> SpyRspRatioResponse:
    cache_key = range_key.upper()
    try:
        return spy_rsp_cache.get_or_set(
            cache_key, lambda: get_spy_rsp_ratio(session, range_key)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/cache/clear")
def api_clear_cache() -> dict:
    clear_all_caches(source="api")
    return {"status": "ok"}


# ============ Realtime APIs (5-minute TTL) ============

@app.get("/api/market/realtime-summary", response_model=MarketSummary)
def api_realtime_market_summary(
    market: str = Query("sp500")
) -> MarketSummary:
    """Get realtime market summary with live quotes (5-min cache)."""
    key = market.lower()
    try:
        return realtime_market_cache.get_or_set(key, lambda: get_realtime_market_summary(market))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/sectors/realtime-summary", response_model=SectorSummaryResponse)
def api_realtime_sector_summary() -> SectorSummaryResponse:
    """Get realtime sector ETF summary with live quotes (5-min cache)."""
    try:
        return realtime_sector_cache.get_or_set("sectors", lambda: get_realtime_sector_summary())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ============ Leveraged ETF Calculator API ============

@app.get("/api/leveraged-etf/calculate", response_model=LeveragedETFResponse)
def api_leveraged_etf_calculate(
    underlying: str = Query("QQQ", description="Underlying ticker symbol"),
    target_price: float = Query(None, description="Target price for underlying (optional)"),
    session: Session = Depends(get_session),
) -> LeveragedETFResponse:
    """
    Calculate leveraged ETF prices for a given underlying ticker.
    Returns underlying info and all related leveraged ETFs with realtime prices.
    """
    try:
        return calculate_leveraged_etf_prices(
            session,
            underlying.strip().upper(),
            target_price if target_price and target_price > 0 else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

