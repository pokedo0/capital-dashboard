from functools import lru_cache
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
            "^GSPC",
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
        default=["NVDA", "GOOG", "AMZN", "AAPL", "META", "MSFT", "TSLA", "AVGO", "TSM"]
    )
    multi_asset_symbols: List[str] = Field(default=["SPY", "GLD", "QQQ", "BTC-USD"])
    timezone: str = "America/New_York"
    # 统一接口缓存 10 分钟，减少重复计算/请求
    cache_ttl_seconds: int = 600


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
