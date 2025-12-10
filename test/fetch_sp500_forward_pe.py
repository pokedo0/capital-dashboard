import re
import json
import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

# 引入 curl_cffi
from curl_cffi import requests

URL = "https://en.macromicro.me/series/20052/sp500-forward-pe-ratio"

# Force UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def fetch_html(url: str) -> str:
    print(f"开始请求: {url}")
    try:
        resp = requests.get(
            url,
            impersonate="chrome110",  # 模拟 Chrome 110 版本
            timeout=20,
        )
        print(f"HTTP {resp.status_code}")
        if "<title>Just a moment...</title>" in resp.text:
            print("错误：依然被 Cloudflare 拦截，可能需要更新 impersonate 或更换 IP。")
        return resp.text
    except Exception as e:
        print(f"请求发生异常: {e}")
        return ""

def extract_series(html: str) -> List[Tuple[int, float]]:
    # 你的原有逻辑
    m = re.search(r'JSON\.parse\(atob\("([A-Za-z0-9+/=]+)"\)\)', html)
    if not m:
        # 调试用：如果找不到，可能是 HTML 结构变了，或者是被拦截页面
        # print("HTML Preview:", html[:500]) 
        raise ValueError("在 HTML 中未找到 Base64 数据段")
    payload = m.group(1)
    decoded = base64.b64decode(payload)
    return json.loads(decoded)

def normalize_series(raw: List[Tuple[int, float]]) -> List[Dict[str, float]]:
    """将毫秒时间戳转换为日期字符串，并保留 PE 数值。"""
    normalized: List[Dict[str, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        ts_ms, value = item[0], item[1]
        try:
            date_str = datetime.utcfromtimestamp(float(ts_ms) / 1000).strftime("%Y-%m-%d")
            pe_value = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        normalized.append({"date": date_str, "pe": pe_value})
    return normalized

def main() -> None:
    html = fetch_html(URL)
    if not html:
        return

    try:
        series = extract_series(html)
        normalized = normalize_series(series)
        print(f"解析成功，共 {len(normalized)} 个数据点。")
        print("最新 5 个点:", normalized[-50:])
    except Exception as exc:
        print(f"解析失败: {exc}")

if __name__ == "__main__":
    main()
