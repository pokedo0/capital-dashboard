# Shepherd Capital Dashboard

前后端分离的美股可视化仪表盘示例。后端使用 FastAPI + SQLite + APScheduler 抓取雅虎行情，前端采用 Vue 3 + Vite + Tailwind + lightweight-charts，实现图片中所列 S&P500 / NASDAQ100 / 多资产图表。

## 目录结构

```
backend/        FastAPI 服务、数据库、scheduler
backend/data/   默认 SQLite 输出目录（market.db 会写在这里）
frontend/       Vue3 单页应用、图表组件
deploy/         docker/nginx 相关文件
```

## 本地开发

### 后端
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\\Scripts\\activate
pip install -r requirements.txt
pip install -e .
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev -- --host
```

## Docker 部署

```bash
docker compose up --build -d
```

- `backend`：运行 FastAPI，SQLite 数据写入 `backend/data/market.db`
- `frontend`：构建静态资源后由 nginx 容器提供
- `proxy`：nginx 反向代理，对外暴露 80 端口，`/api` 转发到后端，其余流量走前端

> 若已有外部代理，可仅运行 `backend` + `frontend` 并调整端口。

## 关键特性回顾

- APScheduler 示例：`app.main` 中在 `startup` 触发 `_refresh_history` 并注册每日 `cron` 任务
- 内存缓存：自建 TTL cache（60s），保证 512MB VPS 内足够轻量
- SQLite 持久化 1~5 年历史数据
- Vue 组件复刻截图中所有图表功能，支持时间范围切换、legend 显隐、全屏放大
- Tailwind + 自定义暗色主题，移动端响应式布局

更多细节可参见 `backend/README.md` 与前端源码注释。
