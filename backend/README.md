# Capital Dashboard Backend

FastAPI 服务负责从 Yahoo Finance 抓取数据、写入 SQLite，并向前端提供行情接口与市场宽度数据。

## 本地运行

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 主要特性

- FastAPI + SQLModel 管理 SQLite 数据库
- APScheduler 每日自动刷新行情（startup 时全量拉取 1~5 年历史）
- yfinance 拉取股票/指数数据；`barchart_api` 拉取市场宽度指标（无 API Key）
- TTL 内存缓存，默认 60 秒
- 通用接口：
  - `/api/ohlcv`
  - `/api/performance/relative`
  - `/api/performance/daily`
  - `/api/market/summary`
  - `/api/sectors/summary`
  - `/api/market/breadth`

## 数据目录

所有 SQLite 文件默认保存在 `backend/data/`，已在 `.gitignore` 中排除。若要备份历史行情，可直接复制该目录或挂载到外部卷。

## 快速测试

```bash
pytest test/test_yfquery.py      # 验证雅虎行情
pytest test/test_barchart_nvda.py  # 验证 Barchart 市场宽度
```
两者都需要网络访问公共接口。
