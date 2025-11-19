from functools import lru_cache
import os
from typing import List

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "Capital Dashboard API"
    database_url: str = Field(default="sqlite:///./data/market.db")
    yahoo_batch_symbols: List[str] = Field(
        default=[
            "SPY",
            "QQQ",
            "^VIX",
            "^NDX",
            "XLC",
            "XLK",
            "XLF",
            "XLV",
            "XLY",
            "XLP",
            "XLE",
            "XLI",
            "XLU",
            "XLB",
            "VNQ",
            "DIA",
        ]
    )
    mag7_symbols: List[str] = Field(
        default=["NVDA", "GOOG", "AMZN", "AAPL", "META", "MSFT", "TSLA"]
    )
    multi_asset_symbols: List[str] = Field(default=["SPY", "GLD", "QQQ", "BTC-USD"])
    timezone: str = "US/Eastern"
    cache_ttl_seconds: int = 60
    barchart_api_key: str | None = Field(default_factory=lambda: os.getenv("BARCHART_API_KEY"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
