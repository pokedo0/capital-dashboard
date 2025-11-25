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
    advancers_pct: Optional[float] = None
    decliners_pct: Optional[float] = None


class SectorItem(BaseModel):
    name: str
    symbol: str
    change_pct: float
    volume_millions: float
    percent_of_avg: float


class SectorSummaryResponse(BaseModel):
    sectors: List[SectorItem]


class ValuePoint(BaseModel):
    time: date
    value: float


class RelativeSeries(BaseModel):
    symbol: str
    points: List[ValuePoint]


class DrawdownResponse(BaseModel):
    symbol: str
    drawdown: List[ValuePoint]
    price: List[ValuePoint]
    current_drawdown: float
    max_drawdown: float


class RelativeToResponse(BaseModel):
    symbol: str
    benchmark: str
    ratio: List[ValuePoint]
    moving_average: List[ValuePoint]


class FearGreedResponse(BaseModel):
    index: List[ValuePoint]
    spy: List[ValuePoint]


class MarketBreadthResponse(BaseModel):
    benchmark_percent: RelativeSeries
    benchmark_price: List[ValuePoint]
    series: List[RelativeSeries]
