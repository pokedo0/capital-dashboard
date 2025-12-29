"""
Realtime market data service using yfinance.
Provides real-time quotes for market summary and sector ETFs.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Force disable curl_cffi to avoid TLS issues
os.environ.setdefault("YF_NO_CURL", "1")
os.environ.setdefault("YF_ENABLE_CURL", "0")
import yfinance as yf  # noqa: E402

from ..schemas.market import MarketSummary, SectorItem, SectorSummaryResponse

logger = logging.getLogger(__name__)

# Sector ETF mapping
SECTOR_ETFS: Dict[str, str] = {
    "XLC": "Comm Services",
    "XLY": "Consumer Disc",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "VNQ": "Real Estate",
    "XLK": "Technology",
    "XLU": "Utilities",
}

# Market index symbols
MARKET_SYMBOLS = {
    "sp500": {"index": "^GSPC", "etf": "SPY"},
    "nasdaq": {"index": "^NDX", "etf": "QQQ"},
}


def _get_realtime_quote(symbol: str) -> Dict:
    """
    Get realtime quote for a single symbol using yfinance.
    Returns dict with price, change, change_pct, volume.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Try to get realtime data from info
        current_price = info.get("regularMarketPrice") or info.get("currentPrice")
        previous_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        
        if current_price and previous_close:
            change = current_price - previous_close
            change_pct = (change / previous_close) * 100 if previous_close else 0
        else:
            change = 0
            change_pct = 0
            
        return {
            "price": current_price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "volume": info.get("regularMarketVolume") or info.get("volume") or 0,
            "avg_volume": info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0,
        }
    except Exception as exc:
        logger.warning("Failed to get realtime quote for %s: %s", symbol, exc)
        return {}


def _get_batch_realtime_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """
    Get realtime quotes for multiple symbols in batch.
    Returns dict mapping symbol to quote data.
    """
    result: Dict[str, Dict] = {}
    
    try:
        # Use yfinance download for batch efficiency
        tickers = yf.Tickers(" ".join(symbols))
        
        for symbol in symbols:
            try:
                ticker = tickers.tickers.get(symbol)
                if not ticker:
                    continue
                    
                info = ticker.info
                current_price = info.get("regularMarketPrice") or info.get("currentPrice")
                previous_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
                
                if current_price and previous_close:
                    change = current_price - previous_close
                    change_pct = (change / previous_close) * 100 if previous_close else 0
                else:
                    change = 0
                    change_pct = 0
                    
                result[symbol] = {
                    "price": current_price,
                    "previous_close": previous_close,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": info.get("regularMarketVolume") or info.get("volume") or 0,
                    "avg_volume": info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0,
                }
            except Exception as exc:
                logger.warning("Failed to get quote for %s: %s", symbol, exc)
                continue
                
    except Exception as exc:
        logger.error("Batch quote fetch failed: %s", exc)
        # Fallback to individual fetches
        for symbol in symbols:
            quote = _get_realtime_quote(symbol)
            if quote:
                result[symbol] = quote
                
    return result


def _fetch_realtime_constituents_changes(url: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Fetch constituents CSV and calculate advance/decline percentages.
    This still uses CSV as source but could be enhanced with realtime data.
    """
    import requests
    from io import StringIO
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
    except Exception as exc:
        logger.warning("Failed to fetch constituents: %s", exc)
        return None, None
    
    if "Symbol" not in df.columns or "Chg" not in df.columns:
        return None, None
    
    total = len(df)
    if total == 0:
        return None, None
    
    advancers = decliners = flats = 0
    for _, row in df.iterrows():
        try:
            chg_str = str(row.get("Chg", "0")).strip().replace("(", "").replace(")", "").replace("%", "")
            chg_val = float(chg_str) if chg_str else 0
        except (ValueError, TypeError):
            continue
            
        if chg_val > 0:
            advancers += 1
        elif chg_val < 0:
            decliners += 1
        else:
            flats += 1
    
    tracked = advancers + decliners + flats
    if tracked == 0:
        return None, None
        
    return (advancers / tracked * 100, decliners / tracked * 100)


def get_realtime_market_summary(market: str) -> MarketSummary:
    """
    Get realtime market summary with live quotes.
    """
    market_key = market.lower()
    
    if market_key not in MARKET_SYMBOLS:
        raise ValueError(f"Unknown market: {market}")
    
    symbols_config = MARKET_SYMBOLS[market_key]
    index_symbol = symbols_config["index"]
    
    logger.info("Fetching realtime market summary for %s", market_key)
    
    # Get realtime quotes for index and VIX
    quotes = _get_batch_realtime_quotes([index_symbol, "^VIX"])
    
    index_quote = quotes.get(index_symbol, {})
    vix_quote = quotes.get("^VIX", {})
    
    if not index_quote.get("price"):
        raise ValueError(f"Unable to fetch realtime data for {index_symbol}")
    
    # Get advance/decline from CSV (still the best source for this)
    advancers_pct: Optional[float] = None
    decliners_pct: Optional[float] = None
    
    if market_key == "sp500":
        url = "https://raw.githubusercontent.com/pokedo0/index-constituents/main/docs/constituents-sp500.csv"
        advancers_pct, decliners_pct = _fetch_realtime_constituents_changes(url)
    elif market_key == "nasdaq":
        url = "https://raw.githubusercontent.com/pokedo0/index-constituents/main/docs/constituents-nasdaq100.csv"
        advancers_pct, decliners_pct = _fetch_realtime_constituents_changes(url)
    
    return MarketSummary(
        market=market.upper(),
        date=date.today(),
        index_value=index_quote.get("price", 0),
        day_change=index_quote.get("change", 0),
        day_change_pct=index_quote.get("change_pct", 0),
        vix_value=vix_quote.get("price", 0),
        vix_change_pct=vix_quote.get("change_pct", 0),
        advancers_pct=advancers_pct,
        decliners_pct=decliners_pct,
    )


def get_realtime_sector_summary() -> SectorSummaryResponse:
    """
    Get realtime sector ETF summary with live quotes.
    """
    logger.info("Fetching realtime sector summary")
    
    symbols = list(SECTOR_ETFS.keys())
    quotes = _get_batch_realtime_quotes(symbols)
    
    items: List[SectorItem] = []
    for symbol, label in SECTOR_ETFS.items():
        quote = quotes.get(symbol, {})
        
        if not quote.get("price"):
            logger.warning("No realtime data for %s", symbol)
            continue
        
        volume = quote.get("volume", 0)
        avg_volume = quote.get("avg_volume", 0)
        
        items.append(
            SectorItem(
                name=label,
                symbol=symbol,
                change_pct=quote.get("change_pct", 0),
                volume_millions=volume / 1_000_000 if volume else 0,
                percent_of_avg=(volume / avg_volume * 100) if avg_volume else 0,
            )
        )
    
    return SectorSummaryResponse(sectors=items)
