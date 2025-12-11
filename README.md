# Shepherd Capital Dashboard

前后端分离的美股可视化仪表盘。后端使用 FastAPI + SQLite + APScheduler 抓取雅虎行情与 Barchart 市场宽度数据，前端采用 Vue 3 + Vite + Tailwind + lightweight-charts 实现多图表可视化。

## 目录结构

```
backend/        FastAPI 服务、数据库、scheduler
backend/data/   默认 SQLite 输出目录（market.db）
frontend/       Vue3 单页应用、图表组件
deploy/         docker/nginx 相关文件
```

## 环境要求

- Python 3.10+
- Node.js 18+（含 npm）
- Docker / Docker Compose（可选，用于一键部署）

## 本地开发

### 后端
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- 默认使用雅虎接口抓取行情，市场宽度数据通过三方库 `barchart_api` 调用公开接口，无需额外 API Key。
- SQLite 文件写入 `backend/data/market.db`，已被 `.gitignore` 忽略。

### 前端
```bash
cd frontend
npm install
npm run dev -- --host
```
- 接口地址通过 `frontend/.env` 配置，默认 `VITE_API_BASE_URL=http://localhost:8000/api`。

### Windows 一键启动
若依赖已安装，可在仓库根目录运行：
```powershell
start-dev.bat  # 可选参数：<backend_host> <backend_port> <frontend_port>
```
脚本会新开两个窗口分别启动后端与前端。

## Docker 部署

```bash
docker compose up --build -d
```

- `backend`：FastAPI，SQLite 数据写入 `backend/data/market.db`
- `frontend`：Vite 构建后由 nginx 提供静态资源
- `proxy`：nginx 反向代理，对外暴露 80 端口，`/api` 转发后端，其余流量走前端

若已有外部代理，可仅运行 `backend` 与 `frontend` 服务并自行暴露端口。

## 快速测试

- 后端：可运行 `pytest test/test_yfquery.py` 或 `pytest test/test_barchart_nvda.py`（需联网）。
- 前端：`npm run build` 验证编译是否通过。

更多细节见 `backend/README.md`，组件与接口说明可阅读对应源码注释。
