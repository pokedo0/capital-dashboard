"""
Schemas for Leveraged ETF API responses.
"""
from typing import List, Optional

from pydantic import BaseModel


class LeveragedETFItem(BaseModel):
    """Individual leveraged ETF data item."""
    ticker: str
    name: str
    direction: str  # "long", "short", or "underlying"
    leverage: str  # e.g., "2x", "3x", "1.5x"
    current_price: Optional[float] = None
    current_change_pct: Optional[float] = None
    ytd_return: Optional[float] = None
    target_change_pct: Optional[float] = None
    target_price: Optional[float] = None
    avg_volume: Optional[float] = None
    aum: Optional[float] = None


class LeveragedETFResponse(BaseModel):
    """Response containing underlying and leveraged ETF data."""
    underlying: LeveragedETFItem
    leveraged_etfs: List[LeveragedETFItem]
    target_underlying_price: float
