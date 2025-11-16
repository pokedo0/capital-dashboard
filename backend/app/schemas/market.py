from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class OHLCVPoint(BaseModel):
    time: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None


class SeriesPayload(BaseModel):
    symbol: str
    points: List[OHLCVPoint]


class MarketSummary(BaseModel):
    market: str
    date: date
    index_value: float
    day_change: float
    day_change_pct: float
    vix_value: float
    vix_change_pct: float


class SectorItem(BaseModel):
    name: str
    symbol: str
    change_pct: float
    volume_millions: float
    percent_of_avg: float


class SectorSummaryResponse(BaseModel):
    sectors: List[SectorItem]
