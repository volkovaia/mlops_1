FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Копируем манифесты и README (обязателен для сборки hatchling)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Копируем модель и исходный код
COPY models/ ./models/
COPY src/ ./src/

# Финальная установка нашего пакета
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "toxic_service.app:app", "--host", "0.0.0.0", "--port", "8000"]