"""
Model for Leveraged ETF data.
"""
from typing import Optional

from sqlmodel import Field, SQLModel


class LeveragedETF(SQLModel, table=True):
    """Stores leveraged ETF mapping data from CSV."""
    __tablename__ = "leveraged_etfs"

    ticker: str = Field(primary_key=True, index=True)
    name: Optional[str] = Field(default=None)
    underlying_asset: Optional[str] = Field(default=None)
    underlying_ticker: str = Field(index=True)
    leverage: str = Field(default="1x")  # e.g., "2x", "3x", "1.5x", "variable"
    direction: str = Field(default="long")  # "long" or "short"
    avg_volume: Optional[float] = Field(default=None)
    aum: Optional[float] = Field(default=None)
