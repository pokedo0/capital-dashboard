"""
Leveraged ETF service for fetching and calculating leveraged ETF data.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from io import StringIO
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from sqlmodel import Session, select

# Force disable curl_cffi to avoid TLS issues
os.environ.setdefault("YF_NO_CURL", "1")
os.environ.setdefault("YF_ENABLE_CURL", "0")
import yfinance as yf  # noqa: E402

from ..models.leveraged_etf import LeveragedETF
from ..schemas.leveraged_etf import (
    LeveragedETFItem,
    LeveragedETFResponse,
)
import math

from .overnight_data import get_overnight_quotes

logger = logging.getLogger(__name__)


def _sanitize_float(value: float | None) -> float | None:
    """Convert NaN/Inf to None for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _is_valid_float(value: float | None) -> bool:
    """Check if a float value is valid (not None, NaN, or Inf)."""
    if value is None:
        return False
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return False
    return True

# CSV data source
LEVERAGED_ETF_CSV_URL = (
    "https://raw.githubusercontent.com/pokedo0/Leveraged-ETF-Data-Scraper/"
    "refs/heads/main/leveraged_etf_filled.csv"
)


def fetch_and_store_leveraged_etf_data(session: Session) -> int:
    """
    Fetch leveraged ETF data from CSV and store in database.
    Returns the number of records inserted/updated.
    """
    logger.info("Fetching leveraged ETF data from %s", LEVERAGED_ETF_CSV_URL)
    
    try:
        response = requests.get(LEVERAGED_ETF_CSV_URL, timeout=30)
        response.raise_for_status()
        
        # Parse CSV
        df = pd.read_csv(StringIO(response.text))
        
        required_columns = ["ticker", "underlying_ticker", "leverage", "direction"]
        for col in required_columns:
            if col not in df.columns:
                logger.error("Missing required column: %s", col)
                return 0
        
        count = 0
        for _, row in df.iterrows():
            ticker = str(row.get("ticker", "")).strip().upper()
            underlying_ticker = str(row.get("underlying_ticker", "")).strip().upper()
            leverage = str(row.get("leverage", "")).strip().lower()
            direction = str(row.get("direction", "")).strip().lower()
            
            # Skip if no ticker or underlying ticker
            if not ticker or not underlying_ticker:
                continue
            
            # Skip variable leverage ETFs
            if leverage == "variable":
                continue
            
            name = str(row.get("name", "")).strip() if pd.notna(row.get("name")) else None
            underlying_asset = (
                str(row.get("underlying_asset", "")).strip()
                if pd.notna(row.get("underlying_asset"))
                else None
            )
            
            # Parse metrics
            avg_volume = None
            if pd.notna(row.get("avg_volume")):
                try:
                    avg_volume = float(row.get("avg_volume"))
                except (ValueError, TypeError):
                    pass
            
            aum = None
            if pd.notna(row.get("aum")):
                try:
                    aum = float(row.get("aum"))
                except (ValueError, TypeError):
                    pass
            
            # Upsert record
            existing = session.exec(
                select(LeveragedETF).where(LeveragedETF.ticker == ticker)
            ).first()
            
            if existing:
                existing.name = name
                existing.underlying_asset = underlying_asset
                existing.underlying_ticker = underlying_ticker
                existing.leverage = leverage
                existing.direction = direction
                existing.avg_volume = avg_volume
                existing.aum = aum
                session.add(existing)
            else:
                etf = LeveragedETF(
                    ticker=ticker,
                    name=name,
                    underlying_asset=underlying_asset,
                    underlying_ticker=underlying_ticker,
                    leverage=leverage,
                    direction=direction,
                    avg_volume=avg_volume,
                    aum=aum,
                )
                session.add(etf)
            
            count += 1
        
        session.commit()
        logger.info("Successfully stored %d leveraged ETF records", count)
        return count
        
    except Exception as exc:
        logger.error("Failed to fetch/store leveraged ETF data: %s", exc)
        session.rollback()
        return 0


def get_leveraged_etfs_for_underlying(
    session: Session, underlying_ticker: str
) -> List[LeveragedETF]:
    """
    Get all leveraged ETFs for a given underlying ticker.
    Filters out variable leverage ETFs.
    """
    underlying = underlying_ticker.strip().upper()
    
    statement = (
        select(LeveragedETF)
        .where(LeveragedETF.underlying_ticker == underlying)
        .where(LeveragedETF.leverage != "variable")
    )
    
    results = session.exec(statement).all()
    
    # Sort:
    # 1. Direction: Long (0) first, Short (1) second
    # 2. Leverage: High to Low
    # 3. AUM: High to Low
    def sort_key(etf: LeveragedETF) -> Tuple[int, float, float]:
        direction_order = 0 if etf.direction == "long" else 1
        try:
            # Extract numeric leverage (e.g., "2x" -> 2.0)
            leverage_num = float(etf.leverage.replace("x", ""))
        except (ValueError, AttributeError):
            leverage_num = 0
            
        aum_val = etf.aum if etf.aum else -1.0
        
        # Tuple comparison:
        # direction_order (asc): 0, 1
        # -leverage_num (asc = desc): -3, -2, -1.5
        # -aum_val (asc = desc)
        return (direction_order, -leverage_num, -aum_val)
    
    return sorted(results, key=sort_key)


def _parse_leverage(leverage_str: str) -> float:
    """Parse leverage string to float. E.g., '2x' -> 2.0"""
    try:
        return float(leverage_str.lower().replace("x", ""))
    except (ValueError, AttributeError):
        return 1.0


def _fetch_single_info(symbol: str) -> Tuple[str, Optional[Dict]]:
    """Fetch ticker.info for a single symbol. Used by ThreadPoolExecutor."""
    try:
        ticker = yf.Ticker(symbol)
        return (symbol, ticker.info)
    except Exception as exc:
        logger.warning("Failed to fetch info for %s: %s", symbol, exc)
        return (symbol, None)


def _get_batch_realtime_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """
    Get realtime quotes for multiple symbols concurrently.
    
    Uses ThreadPoolExecutor to fetch ticker.info in parallel instead of
    sequentially, reducing total wait time from O(n) to O(n/workers).
    
    Priority order for price source:
    1. Overnight (夜盘) - when available during overnight trading hours
    2. Pre-market (盘前) - during pre-market hours
    3. Post-market (盘后) - during after-hours
    4. Regular (常规) - during regular trading hours
    
    Returns dict mapping symbol to quote data.
    """
    result: Dict[str, Dict] = {}
    
    if not symbols:
        return result
    
    # First, try to fetch overnight data for all symbols
    overnight_quotes = get_overnight_quotes(symbols)
    logger.debug("Fetched overnight data for %d symbols", len(overnight_quotes))
    
    # Concurrently fetch ticker.info for all symbols
    info_map: Dict[str, Dict] = {}
    max_workers = min(len(symbols), 8)
    logger.info(
        "Fetching realtime quotes for %d symbols with %d workers",
        len(symbols), max_workers,
    )
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_single_info, symbol): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol, info = future.result()
            if info is not None:
                info_map[symbol] = info
    
    # Process fetched info into quote results
    for symbol in symbols:
        info = info_map.get(symbol)
        if not info:
            continue
        
        try:
            # Get yfinance data for different sessions
            premarket_price = info.get("preMarketPrice")
            postmarket_price = info.get("postMarketPrice")
            regular_price = info.get("regularMarketPrice") or info.get("currentPrice")
            regular_prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
            
            # Default selection
            current_price = None
            previous_close = regular_prev_close
            price_source = "regular"
            change_pct = None
            
            # Check overnight data first (highest priority)
            overnight_data = overnight_quotes.get(symbol)
            if overnight_data and overnight_data.get("price"):
                current_price = overnight_data.get("price")
                if regular_price and regular_price > 0:
                    previous_close = regular_price
                price_source = "overnight"
                change_pct = overnight_data.get("change_pct")
                logger.debug(
                    "Using overnight data for %s: price=%.2f, change=%.2f%%",
                    symbol, current_price, change_pct or 0
                )
            
            elif premarket_price and premarket_price > 0:
                current_price = premarket_price
                if regular_price and regular_price > 0:
                    previous_close = regular_price
                price_source = "premarket"
                change_pct = info.get("preMarketChangePercent")
                
            elif postmarket_price and postmarket_price > 0:
                current_price = postmarket_price
                if regular_price and regular_price > 0:
                    previous_close = regular_price
                price_source = "postmarket"
                change_pct = info.get("postMarketChangePercent")
                
            elif regular_price and regular_price > 0:
                current_price = regular_price
                previous_close = regular_prev_close
                price_source = "regular"
            
            # Fallback if specific price is missing
            if not current_price:
                current_price = regular_price or premarket_price or postmarket_price
            if not previous_close:
                previous_close = regular_prev_close
            
            # If explicit change percent is missing, calculate manually
            if change_pct is None:
                if current_price and previous_close and previous_close > 0:
                    change_pct = ((current_price - previous_close) / previous_close) * 100
            
            # YTD return will be calculated in the second pass below
            # (ytdReturn from info is NOT year-to-date; it's a fund lifetime metric)
            
            result[symbol] = {
                "price": _sanitize_float(current_price),
                "previous_close": _sanitize_float(previous_close),
                "change": _sanitize_float((current_price - previous_close) if current_price and previous_close else 0),
                "change_pct": _sanitize_float(change_pct),
                "ytd_return": None,
                "price_source": price_source,
            }
            
            logger.debug(
                "Quote for %s: price=%.2f (%s), change=%.2f%%",
                symbol, current_price or 0, price_source, change_pct or 0
            )
            
        except Exception as exc:
            logger.warning("Failed to process quote for %s: %s", symbol, exc)
            continue
    
    # Calculate YTD for all symbols via a single batch yf.download()
    # YTD baseline = last trading day close of the PREVIOUS year (matches Yahoo Finance).
    # yfinance info's ytdReturn is a fund lifetime metric, NOT year-to-date.
    ytd_symbols = [
        s for s in symbols
        if s in result and result[s].get("price")
    ]
    if ytd_symbols:
        logger.info("Fetching YTD data for %d symbols: %s", len(ytd_symbols), ytd_symbols)
        try:
            current_year = datetime.now().year
            # Download last ~10 days of previous year to find the last trading day
            prev_year_start = datetime(current_year - 1, 12, 20)
            prev_year_end = datetime(current_year, 1, 1)  # exclusive end
            hist = yf.download(
                ytd_symbols,
                start=prev_year_start,
                end=prev_year_end,
                progress=False,
                threads=True,
            )
            if not hist.empty:
                for sym in ytd_symbols:
                    try:
                        # yfinance may return MultiIndex columns (Price, Ticker)
                        # even for single-ticker downloads in newer versions.
                        # Always try symbol-indexed access first.
                        close_data = hist["Close"]
                        if isinstance(close_data, pd.DataFrame) and sym in close_data.columns:
                            close_col = close_data[sym]
                        elif isinstance(close_data, pd.Series):
                            close_col = close_data
                        elif isinstance(close_data, pd.DataFrame) and close_data.shape[1] == 1:
                            close_col = close_data.iloc[:, 0]
                        else:
                            logger.warning("Could not extract Close for %s from columns: %s", sym, list(close_data.columns) if hasattr(close_data, 'columns') else type(close_data))
                            continue
                        
                        valid = close_col.dropna()
                        if valid.empty:
                            logger.info("No valid Close data for %s in prev-year-end period", sym)
                            continue
                        
                        # Use the LAST close of the previous year as baseline
                        last_close_prev_year = float(valid.iloc[-1])
                        current = result[sym].get("price")
                        if last_close_prev_year > 0 and current:
                            ytd_pct = ((current - last_close_prev_year) / last_close_prev_year) * 100
                            result[sym]["ytd_return"] = _sanitize_float(ytd_pct)
                            logger.info("YTD for %s: %.2f%% (prev-year-end close=%.2f, current=%.2f)", sym, ytd_pct, last_close_prev_year, current)
                        else:
                            logger.info("Skipping YTD for %s: last_close_prev_year=%.2f, current=%s", sym, last_close_prev_year, current)
                    except Exception as exc:
                        logger.warning("Failed to calculate YTD for %s: %s", sym, exc)
            else:
                logger.warning("yf.download returned empty DataFrame for YTD symbols: %s", ytd_symbols)
        except Exception as exc:
            logger.warning("Batch YTD download failed: %s", exc)
    
    return result


def calculate_leveraged_etf_prices(
    session: Session,
    underlying_ticker: str,
    target_price: Optional[float] = None,
) -> LeveragedETFResponse:
    """
    Calculate leveraged ETF prices for a given underlying ticker.
    
    Args:
        session: Database session
        underlying_ticker: The underlying ticker symbol (e.g., "NVDA", "QQQ")
        target_price: Optional target price for the underlying. If None, uses current price.
    
    Returns:
        LeveragedETFResponse with underlying and leverage ETF data
    """
    underlying = underlying_ticker.strip().upper()
    
    # Get leveraged ETFs from database
    leveraged_etfs = get_leveraged_etfs_for_underlying(session, underlying)
    
    # Collect all symbols to fetch (underlying + leveraged ETFs)
    all_symbols = [underlying] + [etf.ticker for etf in leveraged_etfs]
    
    # Fetch realtime quotes for all symbols in one batch
    quotes = _get_batch_realtime_quotes(all_symbols)
    
    underlying_quote = quotes.get(underlying, {})
    underlying_price = underlying_quote.get("price")
    underlying_prev_close = underlying_quote.get("previous_close")
    underlying_change_pct = underlying_quote.get("change_pct", 0)
    underlying_ytd = underlying_quote.get("ytd_return")
    
    if not underlying_price:
        raise ValueError(f"Unable to fetch price for {underlying}")
    
    # Use current price as target if not provided
    if target_price is None:
        target_price = underlying_price
    
    # Calculate target change percentage for underlying
    # Calculate Incremental Change for underlying
    if underlying_price and underlying_price > 0:
        incremental_change_pct = (target_price - underlying_price) / underlying_price
    else:
        incremental_change_pct = 0
    
    # Calculate Target Change for underlying based on Prev Close
    if underlying_prev_close and underlying_prev_close > 0:
        target_change_pct = ((target_price - underlying_prev_close) / underlying_prev_close) * 100
    else:
        target_change_pct = 0
    
    # Build underlying item
    underlying_item = LeveragedETFItem(
        ticker=underlying,
        name=f"{underlying} (Underlying)",
        direction="underlying",
        leverage="1x",
        current_price=_sanitize_float(underlying_price),
        current_change_pct=_sanitize_float(underlying_change_pct),
        ytd_return=_sanitize_float(underlying_ytd),
        target_change_pct=_sanitize_float(target_change_pct),
        target_price=_sanitize_float(target_price),
    )
    
    # Build leveraged ETF items
    items: List[LeveragedETFItem] = []
    
    for etf in leveraged_etfs:
        etf_quote = quotes.get(etf.ticker, {})
        etf_price = etf_quote.get("price")
        # In this context, previous_close has been normalized to the correct baseline (e.g. yesterday's close)
        etf_prev_close = etf_quote.get("previous_close")
        etf_change_pct = etf_quote.get("change_pct", 0)
        etf_ytd = etf_quote.get("ytd_return")
        
        # Skip ETFs with no price data (possibly delisted or no trading data)
        if not etf_price or not etf_prev_close:
            logger.debug("Skipping %s: no price data available", etf.ticker)
            continue
        
        # Validate price data - skip if NaN or invalid
        if not _is_valid_float(etf_price) or not _is_valid_float(etf_prev_close):
            logger.debug("Skipping %s: invalid price data (NaN/Inf)", etf.ticker)
            continue
        
        # Parse leverage
        leverage_num = _parse_leverage(etf.leverage)
        
        # Calculate ETF Incremental Pct
        if etf.direction == "long":
            etf_incremental_pct = incremental_change_pct * leverage_num
        else:  # short
            etf_incremental_pct = -incremental_change_pct * leverage_num
            
        # Calculate ETF Target Price based on CURRENT Price (Incremental)
        etf_target_price = etf_price * (1 + etf_incremental_pct)
        
        # Calculate ETF Target Change
        # Fix: Use current_change + leveraged_incremental to ensure consistency
        # When target_price == current_price, target_change should equal current_change
        # This avoids issues with ETFs that lack pre/post market data
        etf_target_change_pct = (etf_change_pct or 0) + (etf_incremental_pct * 100)
        
        # Final validation - skip if calculated values are NaN
        if not _is_valid_float(etf_target_price) or not _is_valid_float(etf_target_change_pct):
            logger.debug("Skipping %s: calculated values are invalid (NaN/Inf)", etf.ticker)
            continue
        
        items.append(
            LeveragedETFItem(
                ticker=etf.ticker,
                name=etf.name or etf.ticker,
                direction=etf.direction,
                leverage=etf.leverage,
                current_price=_sanitize_float(etf_price),
                current_change_pct=_sanitize_float(etf_change_pct),
                ytd_return=_sanitize_float(etf_ytd),
                target_change_pct=_sanitize_float(etf_target_change_pct),
                target_price=_sanitize_float(round(etf_target_price, 2) if etf_target_price else None),
                avg_volume=_sanitize_float(etf.avg_volume),
                aum=_sanitize_float(etf.aum),
            )
        )
    
    return LeveragedETFResponse(
        underlying=underlying_item,
        leveraged_etfs=items,
        target_underlying_price=target_price,
    )
