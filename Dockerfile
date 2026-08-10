# SmartRAG 多阶段构建：base 装依赖，backend/frontend 两个 target 共享
FROM python:3.14-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

FROM base AS backend
WORKDIR /app/backend
EXPOSE 8000
# 容器里不用 python main.py（那是 reload 开发模式）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS frontend
WORKDIR /app/frontend
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
