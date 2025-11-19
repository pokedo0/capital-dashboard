from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
import os
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def _format_date(value: date | str | None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) == 10 and stripped.count("-") == 2:
        return stripped.replace("-", "")
    return stripped


@dataclass
class ApiResponse:
    status_code: int
    text: str


class Api:
    """
    Minimal Barchart OnDemand client for fetching historical CSV data.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://ondemand.websol.barchart.com/getHistory.csv",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.getenv("BARCHART_API_KEY")
        self.base_url = base_url
        self.timeout = timeout

    def _build_params(
        self,
        symbol: str,
        start_date: date | str | None,
        end_date: date | str | None,
        frequency: str,
        interval: int | None,
        order: str,
        max_records: int | None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "apikey": self._require_api_key(),
            "symbol": symbol,
            "type": frequency,
            "order": order,
            "format": "csv",
        }
        start_str = _format_date(start_date)
        end_str = _format_date(end_date)
        if start_str:
            params["startDate"] = start_str
        if end_str:
            params["endDate"] = end_str
        if interval:
            params["interval"] = interval
        if max_records:
            params["maxRecords"] = max_records
        return params

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("Barchart API key is not configured. Set BARCHART_API_KEY.")
        return self.api_key

    def get_stock(
        self,
        symbol: str,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        frequency: str = "daily",
        interval: int | None = None,
        order: str = "asc",
        max_records: int | None = None,
    ) -> ApiResponse:
        """
        Fetch CSV history rows for the requested symbol.
        """

        params = self._build_params(symbol, start_date, end_date, frequency, interval, order, max_records)
        query = urlencode(params)
        request = Request(
            f"{self.base_url}?{query}",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CapitalDashboardBot/1.0)",
                "Accept": "text/csv, */*;q=0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
                return ApiResponse(status_code=status, text=text)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
            logger.warning(
                "Barchart API request failed: %s (status=%s)", exc.reason, getattr(exc, "code", 0)
            )
            return ApiResponse(status_code=getattr(exc, "code", 500), text=body)
        except URLError as exc:
            logger.error("Unable to reach Barchart API: %s", exc.reason)
            raise
