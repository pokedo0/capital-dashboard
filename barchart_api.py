from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from http.cookiejar import CookieJar
import logging
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote, unquote
from urllib.request import HTTPCookieProcessor, Request, build_opener

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) CapitalDashboard/1.0"
BOOTSTRAP_URL = "https://www.barchart.com/"
REFERER_URL = "https://www.barchart.com/stocks/quotes/{symbol}/overview"


def _format_date(value: date | str | None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


@dataclass
class ApiResponse:
    status_code: int
    text: str


class Api:
    """
    Lightweight client that mimics the browser requests sent to
    https://www.barchart.com/proxies/timeseries/query so we can fetch CSV data
    without a dedicated API key.
    """

    def __init__(
        self,
        base_url: str = "https://www.barchart.com/proxies/timeseries/query",
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._cookie_jar = CookieJar()
        self._opener = build_opener(HTTPCookieProcessor(self._cookie_jar))

    def _ensure_session(self) -> None:
        if any(cookie.name == "XSRF-TOKEN" for cookie in self._cookie_jar):
            return
        request = Request(
            BOOTSTRAP_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            self._opener.open(request, timeout=self.timeout).read()
        except HTTPError as exc:
            logger.warning("Bootstrap request failed: status=%s", getattr(exc, "code", 0))
        except URLError as exc:
            logger.error("Unable to reach Barchart website: %s", exc.reason)
            raise

    def _xsrf_token(self) -> Optional[str]:
        for cookie in self._cookie_jar:
            if cookie.name == "XSRF-TOKEN":
                return unquote(cookie.value)
        return None

    def _build_headers(self, symbol: str) -> Dict[str, str]:
        referer_symbol = quote(symbol, safe="")
        headers: Dict[str, str] = {
            "User-Agent": USER_AGENT,
            "Accept": "text/csv, */*;q=0.1",
            "Referer": REFERER_URL.format(symbol=referer_symbol),
            "X-Requested-With": "XMLHttpRequest",
        }
        token = self._xsrf_token()
        if token:
            headers["x-xsrf-token"] = token
        return headers

    def _build_params(
        self,
        symbol: str,
        start_date: date | str | None,
        end_date: date | str | None,
        order: str,
        max_records: int | None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "symbol": symbol,
            "type": "bar",
            "interval": "daily",
            "order": order,
            "format": "csv",
        }
        start_str = _format_date(start_date)
        end_str = _format_date(end_date)
        if start_str:
            params["startDate"] = start_str
        if end_str:
            params["endDate"] = end_str
        if max_records:
            params["limit"] = max_records
        return params

    def _execute(self, request: Request) -> ApiResponse:
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
                return ApiResponse(status_code=status, text=text)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
            logger.warning(
                "Barchart proxy request failed: %s (status=%s)", exc.reason, getattr(exc, "code", 0)
            )
            return ApiResponse(status_code=getattr(exc, "code", 500), text=body)

    def get_stock(
        self,
        symbol: str,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        order: str = "asc",
        max_records: int | None = None,
    ) -> ApiResponse:
        """
        Fetch CSV history rows for the requested breadth symbol via Barchart's public proxy.
        """

        self._ensure_session()
        params = self._build_params(symbol, start_date, end_date, order, max_records)
        query = urlencode(params)
        headers = self._build_headers(symbol)
        request = Request(f"{self.base_url}?{query}", headers=headers)
        response = self._execute(request)
        if response.status_code in (401, 403):
            # Session might have expired; refresh once.
            self._cookie_jar.clear()
            self._ensure_session()
            headers = self._build_headers(symbol)
            request = Request(f"{self.base_url}?{query}", headers=headers)
            response = self._execute(request)
        return response
