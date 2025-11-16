# Capital Dashboard Backend

FastAPI 服务负责从 Yahoo Finance 抓取数据、写入 SQLite，并向前端提供统一的行情接口。

## 本地运行

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\\Scripts\\activate
pip install -r requirements.txt
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 主要特性

- FastAPI + SQLModel 管理 SQLite 数据库
- APScheduler 每日自动刷新行情
- yfinance 拉取 1~5 年历史数据
- TTL 内存缓存，默认 60 秒
- 通用接口
  - `/api/ohlcv`
  - `/api/performance/relative`
  - `/api/performance/daily`
  - `/api/market/summary`
  - `/api/sectors/summary`

## 数据目录

所有 SQLite 文件默认保存在 `backend/data/`，目录已经在仓库中创建 `.gitkeep`，数据库文件将被 `.gitignore` 排除。若要备份历史行情，可直接复制该目录或将其挂载到外部卷。
