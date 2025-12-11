FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 基础依赖用于构建 wheel，安装完成后自动清理 apt 缓存
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，便于 Docker 层缓存
COPY requirements.txt pyproject.toml README.md ./

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# 复制源码与数据目录（数据库路径挂载到 /app/data）
COPY app ./app
COPY data ./data

# 安装本地包（便于引用包元数据）
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
