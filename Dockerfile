FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Копируем указатели DVC и настраиваем работу без Git
COPY .dvc/config ./.dvc/config
COPY data/*.dvc ./data/
RUN uv run --no-sync dvc config --local core.no_scm true

COPY models/ ./models/
COPY src/ ./src/
COPY scripts/ ./scripts/

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "toxic_service.app:app", "--host", "0.0.0.0", "--port", "8000"]