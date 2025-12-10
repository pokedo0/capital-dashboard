from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime
from typing import List

from curl_cffi import requests
from sqlmodel import Session, select

from ..models.price import PriceRecord
from ..schemas.market import ForwardPeResponse, ValuePoint
from .market_data import ensure_history
from .time_ranges import resolve_range_end, resolve_range_start

logger = logging.getLogger(__name__)

FORWARD_PE_URL = "https://en.macromicro.me/series/20052/sp500-forward-pe-ratio"
BASE64_PATTERN = re.compile(r'JSON\.parse\(atob\("([A-Za-z0-9+/=]+)"\)\)')


def _extract_points(html: str) -> List[ValuePoint]:
    match = BASE64_PATTERN.search(html)
    if not match:
        raise ValueError("无法在来源页面解析 Forward P/E 数据")
    payload = match.group(1)
    try:
        decoded = base64.b64decode(payload)
        rows = json.loads(decoded)
    except Exception as exc:  # pragma: no cover - network/format issues
        logger.error("Forward P/E 数据解码失败: %s", exc)
        raise ValueError("Forward P/E 数据格式错误") from exc

    points: List[ValuePoint] = []
    for entry in rows:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        timestamp, value = entry[0], entry[1]
        try:
            ts_ms = float(timestamp)
            val = float(value)
        except (TypeError, ValueError):
            continue
        try:
            date_value = datetime.utcfromtimestamp(ts_ms / 1000).date()
        except Exception:
            continue
        points.append(ValuePoint(time=date_value, value=val))
    points.sort(key=lambda item: item.time)
    if not points:
        raise ValueError("Forward P/E 数据为空")
    return points


def _fetch_forward_pe_history() -> List[ValuePoint]:
    try:
        response = requests.get(
            FORWARD_PE_URL,
            timeout=20,
            impersonate="chrome110",
        )
    except Exception as exc:  # pragma: no cover - network issues
        logger.error("请求 Forward P/E 源失败: %s", exc)
        raise ValueError("无法获取 Forward P/E 数据") from exc

    if response.status_code != 200:
        logger.error("Forward P/E 请求返回非 200 状态码: %s", response.status_code)
        raise ValueError("无法获取 Forward P/E 数据")

    if "Just a moment" in response.text:
        logger.error("Forward P/E 页面被反爬拦截")
        raise ValueError("Forward P/E 数据被反爬拦截，请稍后重试")

    return _extract_points(response.text)


def get_forward_pe_comparison(session: Session, range_key: str) -> ForwardPeResponse:
    start = resolve_range_start(range_key)
    end = resolve_range_end()
    history = _fetch_forward_pe_history()
    forward_pe_points = [point for point in history if start <= point.time <= end]
    if not forward_pe_points:
        raise ValueError("所选区间缺少 Forward P/E 数据")

    benchmark_symbol = "^GSPC"
    ensure_history(session, benchmark_symbol, start, end)
    spx_rows = (
        session.exec(
            select(PriceRecord)
            .where(PriceRecord.symbol == benchmark_symbol)
            .where(PriceRecord.trade_date.between(start, end))
            .order_by(PriceRecord.trade_date)
        )
        .unique()
        .all()
    )
    spx_points = [
        ValuePoint(time=row.trade_date, value=row.close)
        for row in spx_rows
        if row.close is not None
    ]
    if not spx_points:
        raise ValueError("无法获取 S&P 500 指数数据")

    # 将 Forward P/E 以“向前填充”方式对齐到指数交易日，避免 hover 缺失
    aligned_pe: List[ValuePoint] = []
    forward_iter = iter(forward_pe_points)
    current_pe = None
    next_pe = next(forward_iter, None)
    for spx_point in spx_points:
        while next_pe and next_pe.time <= spx_point.time:
            current_pe = next_pe
            next_pe = next(forward_iter, None)
        if current_pe:
            aligned_pe.append(ValuePoint(time=spx_point.time, value=current_pe.value))

    return ForwardPeResponse(forward_pe=aligned_pe, spx=spx_points)
