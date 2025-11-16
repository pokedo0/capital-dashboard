from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class PriceRecord(SQLModel, table=True):
    __tablename__ = "prices"

    symbol: str = Field(primary_key=True, index=True)
    trade_date: date = Field(primary_key=True, index=True)
    open: Optional[float] = Field(default=None)
    high: Optional[float] = Field(default=None)
    low: Optional[float] = Field(default=None)
    close: Optional[float] = Field(default=None)
    volume: Optional[float] = Field(default=None)
