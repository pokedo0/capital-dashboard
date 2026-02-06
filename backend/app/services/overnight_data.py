"""
Yahoo Finance Overnight Trading Data Service

This module provides functionality to fetch overnight trading data from Yahoo Finance.
Overnight trading refers to extended-hours trading outside regular market hours.

US Market Trading Sessions (Eastern Time):
- Regular Market: 9:30 AM - 4:00 PM EST
- Post-Market (After-hours): 4:00 PM - 8:00 PM EST
- Overnight: 8:00 PM - 4:00 AM EST (next day)
- Pre-Market: 4:00 AM - 9:30 AM EST
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional

try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False
    curl_requests = None

logger = logging.getLogger(__name__)


# Try to use zoneinfo (Python 3.9+) for proper DST handling
try:
    from zoneinfo import ZoneInfo
    US_EASTERN = ZoneInfo("America/New_York")
    ZONEINFO_AVAILABLE = True
except ImportError:
    # Fallback for older Python versions
    ZONEINFO_AVAILABLE = False
    US_EASTERN = None
    logger.warning("zoneinfo not available, using fixed UTC-5 offset (DST not handled)")


class MarketSession(Enum):
    """Enum representing different market trading sessions."""
    REGULAR = "regular"      # 9:30 AM - 4:00 PM ET
    POST_MARKET = "postmarket"  # 4:00 PM - 8:00 PM ET
    OVERNIGHT = "overnight"   # 8:00 PM - 4:00 AM ET (next day)
    PRE_MARKET = "premarket"  # 4:00 AM - 9:30 AM ET


# Trading session time boundaries (Eastern Time)
# Using time objects for better readability
from datetime import time as dt_time

class MarketHours:
    """US stock market trading hours (Eastern Time)."""
    PRE_MARKET_START = dt_time(4, 0)    # 4:00 AM
    REGULAR_START = dt_time(9, 30)       # 9:30 AM  
    POST_MARKET_START = dt_time(16, 0)   # 4:00 PM (regular close)
    OVERNIGHT_START = dt_time(20, 0)     # 8:00 PM (post-market close)
    # Note: Overnight ends at PRE_MARKET_START (4:00 AM next day)


def _get_eastern_time_now() -> datetime:
    """
    Get current time in US Eastern timezone with proper DST handling.
    
    Returns:
        datetime object representing current time in US Eastern timezone
    """
    utc_now = datetime.now(timezone.utc)
    
    if ZONEINFO_AVAILABLE and US_EASTERN:
        # Proper timezone conversion with DST support
        return utc_now.astimezone(US_EASTERN)
    else:
        # Fallback: use fixed EST offset (UTC-5), doesn't handle DST
        est_offset = timedelta(hours=-5)
        return utc_now + est_offset


def get_current_market_session() -> MarketSession:
    """
    Determine the current US market trading session based on Eastern Time.
    
    Properly handles DST transitions (EST ↔ EDT) using zoneinfo.
    
    Trading Sessions:
    - Overnight:   8:00 PM - 4:00 AM ET (夜盘)
    - Pre-market:  4:00 AM - 9:30 AM ET (盘前)
    - Regular:     9:30 AM - 4:00 PM ET (常规)
    - Post-market: 4:00 PM - 8:00 PM ET (盘后)
    
    Returns:
        MarketSession enum value indicating current session
    """
    # Get current time in Eastern timezone
    et_now = _get_eastern_time_now()
    current_time = et_now.time()  # Extract time component
    
    # Session determination using time comparisons
    if current_time < MarketHours.PRE_MARKET_START:
        # 12:00 AM - 4:00 AM -> Overnight (continuation from previous day)
        return MarketSession.OVERNIGHT
    elif current_time < MarketHours.REGULAR_START:
        # 4:00 AM - 9:30 AM -> Pre-market
        return MarketSession.PRE_MARKET
    elif current_time < MarketHours.POST_MARKET_START:
        # 9:30 AM - 4:00 PM -> Regular
        return MarketSession.REGULAR
    elif current_time < MarketHours.OVERNIGHT_START:
        # 4:00 PM - 8:00 PM -> Post-market
        return MarketSession.POST_MARKET
    else:
        # 8:00 PM - 12:00 AM -> Overnight
        return MarketSession.OVERNIGHT


def is_overnight_session() -> bool:
    """
    Check if current time is during overnight trading session.
    
    Returns:
        True if currently in overnight session (8PM-4AM EST), False otherwise
    """
    return get_current_market_session() == MarketSession.OVERNIGHT


class OvernightDataService:
    """Service for fetching overnight trading data from Yahoo Finance."""
    
    def __init__(self) -> None:
        """Initialize the overnight data service."""
        self._session = None
        if CURL_AVAILABLE:
            self._session = curl_requests.Session(impersonate="chrome")
    
    @staticmethod
    def _extract_raw_value(value) -> float | None:
        """Extract raw numeric value from Yahoo Finance response format."""
        if isinstance(value, dict):
            return value.get("raw")
        return value
    
    def get_overnight_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get overnight trading data for a single symbol.
        
        Args:
            symbol: Stock ticker symbol (e.g., "NVDA", "QQQ")
            
        Returns:
            Dictionary with overnight data or None if not available:
            - symbol: The stock symbol
            - price: Overnight market price
            - change: Price change from regular close
            - change_pct: Percentage change from regular close
            - time: Time of the overnight quote
            - regular_close: Regular market closing price
        """
        if not CURL_AVAILABLE or not self._session:
            logger.debug("curl_cffi not available, skipping overnight data for %s", symbol)
            return None
        
        try:
            resp = self._session.get(
                f"https://finance.yahoo.com/quote/{symbol}",
                timeout=15
            )
            
            # Parse the embedded JSON data from Yahoo Finance page
            for match in re.finditer(r'"body":"(\{.*?quoteResponse.*?\})"', resp.text):
                try:
                    # Unescape JSON string
                    json_str = match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                    data = json.loads(json_str)
                    
                    quote = data.get("quoteResponse", {}).get("result", [{}])[0]
                    
                    # Check if overnight data is available
                    if "overnightMarketPrice" in quote:
                        overnight_time = self._extract_raw_value(quote.get("overnightMarketTime"))
                        overnight_price = self._extract_raw_value(quote.get("overnightMarketPrice"))
                        overnight_change = self._extract_raw_value(quote.get("overnightMarketChange"))
                        overnight_pct = self._extract_raw_value(quote.get("overnightMarketChangePercent"))
                        regular_close = self._extract_raw_value(quote.get("regularMarketPrice"))
                        
                        return {
                            "symbol": symbol,
                            "price": overnight_price,
                            "change": overnight_change,
                            "change_pct": overnight_pct,
                            "time": datetime.fromtimestamp(overnight_time).strftime("%H:%M:%S") if overnight_time else None,
                            "regular_close": regular_close,
                        }
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                    
        except Exception as exc:
            logger.warning("Failed to fetch overnight data for %s: %s", symbol, exc)
        
        return None
    
    def get_overnight_quotes_batch(
        self, 
        symbols: List[str], 
        max_workers: int = 5
    ) -> Dict[str, Dict]:
        """
        Get overnight trading data for multiple symbols concurrently.
        
        Args:
            symbols: List of stock ticker symbols
            max_workers: Maximum number of concurrent threads
            
        Returns:
            Dictionary mapping symbol to overnight data
        """
        if not CURL_AVAILABLE:
            logger.debug("curl_cffi not available, returning empty overnight data")
            return {}
        
        result: Dict[str, Dict] = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            quotes = list(executor.map(self.get_overnight_quote, symbols))
            
            for quote in quotes:
                if quote:
                    result[quote["symbol"]] = quote
        
        logger.debug("Fetched overnight data for %d/%d symbols", len(result), len(symbols))
        return result


# Global singleton instance for reuse
_overnight_service: Optional[OvernightDataService] = None


def get_overnight_service() -> OvernightDataService:
    """Get or create the global overnight data service instance."""
    global _overnight_service
    if _overnight_service is None:
        _overnight_service = OvernightDataService()
    return _overnight_service


def get_overnight_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """
    Convenience function to get overnight quotes for multiple symbols.
    
    IMPORTANT: This function only returns data during overnight trading hours
    (8:00 PM - 4:00 AM EST). During other sessions, it returns an empty dict.
    
    Args:
        symbols: List of stock ticker symbols
        
    Returns:
        Dictionary mapping symbol to overnight data (empty if not overnight session)
    """
    # Only fetch overnight data during overnight trading hours
    if not is_overnight_session():
        current_session = get_current_market_session()
        logger.debug(
            "Not in overnight session (current: %s), skipping overnight data fetch",
            current_session.value
        )
        return {}
    
    return get_overnight_service().get_overnight_quotes_batch(symbols)

