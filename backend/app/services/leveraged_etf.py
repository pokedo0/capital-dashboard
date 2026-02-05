"""
Leveraged ETF service for fetching and calculating leveraged ETF data.
"""

from __future__ import annotations

import logging
import os
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

logger = logging.getLogger(__name__)

# CSV data source
LEVERAGED_ETF_CSV_URL = (
    "https://github.com/pokedo0/Leveraged-ETF-Data-Scraper/"
    "raw/refs/heads/main/leveraged_etf_data.csv"
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


def _get_batch_realtime_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """
    Get realtime quotes for multiple symbols in batch.
    Prefers premarket/postmarket prices when available.
    Returns dict mapping symbol to quote data.
    """
    result: Dict[str, Dict] = {}
    
    if not symbols:
        return result
    
    try:
        # Use yfinance Tickers for batch efficiency
        tickers = yf.Tickers(" ".join(symbols))
        
        for symbol in symbols:
            try:
                ticker = tickers.tickers.get(symbol)
                if not ticker:
                    continue
                
                info = ticker.info
                
                # Try to get data for different sessions
                premarket_price = info.get("preMarketPrice")
                postmarket_price = info.get("postMarketPrice")
                regular_price = info.get("regularMarketPrice") or info.get("currentPrice")
                regular_prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
                
                # Default selection
                current_price = None
                previous_close = regular_prev_close
                price_source = "regular"
                
                # Determine session and correct previous_close
                if premarket_price and premarket_price > 0:
                    # Pre-market session: 
                    # Current = Pre-market price
                    # Base = Regular Market Price (Yesterday's Close)
                    current_price = premarket_price
                    if regular_price and regular_price > 0:
                        previous_close = regular_price
                    price_source = "premarket"
                    
                elif postmarket_price and postmarket_price > 0:
                    # Post-market session:
                    # Current = Post-market price
                    # Base = Regular Market Price (Today's Close)
                    current_price = postmarket_price
                    if regular_price and regular_price > 0:
                        previous_close = regular_price
                    price_source = "postmarket"
                    
                elif regular_price and regular_price > 0:
                    # Regular session:
                    # Current = Regular price
                    # Base = Regular Market Previous Close
                    current_price = regular_price
                    previous_close = regular_prev_close
                    price_source = "regular"
                
                # Fallback if specific price is missing
                if not current_price:
                    current_price = regular_price or premarket_price or postmarket_price
                if not previous_close:
                    previous_close = regular_prev_close

                # Get change percentages
                # Note: yfinance returns change percent as percentage (e.g., 1.98 means 1.98%)
                change_pct = 0
                
                if price_source == "premarket":
                    change_pct = info.get("preMarketChangePercent")
                elif price_source == "postmarket":
                    change_pct = info.get("postMarketChangePercent")
                
                # If explicit change percent is missing, calculate manually based on selected previous_close
                if change_pct is None:
                    if current_price and previous_close and previous_close > 0:
                        change_pct = ((current_price - previous_close) / previous_close) * 100
                
                # For YTD calculation
                ytd_return = None
                try:
                    # Get the first trading day of the year
                    year_start = datetime(datetime.now().year, 1, 1)
                    hist = ticker.history(start=year_start, end=datetime.now())
                    if not hist.empty:
                        first_close = hist["Close"].iloc[0]
                        if current_price and first_close:
                            ytd_return = ((current_price - first_close) / first_close) * 100
                except Exception:
                    pass
                
                result[symbol] = {
                    "price": current_price,
                    "previous_close": previous_close,
                    "change": (current_price - previous_close) if current_price and previous_close else 0,
                    "change_pct": change_pct,
                    "ytd_return": ytd_return,
                    "price_source": price_source,  # For debugging
                }
                
                logger.debug(
                    "Quote for %s: price=%.2f (%s), change=%.2f%%",
                    symbol, current_price or 0, price_source, change_pct
                )
                
            except Exception as exc:
                logger.warning("Failed to get quote for %s: %s", symbol, exc)
                continue
                
    except Exception as exc:
        logger.error("Batch quote fetch failed: %s", exc)
    
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
        current_price=underlying_price,
        current_change_pct=underlying_change_pct,
        ytd_return=underlying_ytd,
        target_change_pct=target_change_pct,
        target_price=target_price,
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
        
        if not etf_price or not etf_prev_close:
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
        
        # Calculate ETF Target Change vs Prev Close
        if etf_prev_close > 0:
            etf_target_change_pct = ((etf_target_price - etf_prev_close) / etf_prev_close) * 100
        else:
            etf_target_change_pct = 0
        
        items.append(
            LeveragedETFItem(
                ticker=etf.ticker,
                name=etf.name or etf.ticker,
                direction=etf.direction,
                leverage=etf.leverage,
                current_price=etf_price,
                current_change_pct=etf_change_pct,
                ytd_return=etf_ytd,
                target_change_pct=etf_target_change_pct,
                target_price=round(etf_target_price, 2),
                avg_volume=etf.avg_volume,
                aum=etf.aum,
            )
        )
    
    return LeveragedETFResponse(
        underlying=underlying_item,
        leveraged_etfs=items,
        target_underlying_price=target_price,
    )
