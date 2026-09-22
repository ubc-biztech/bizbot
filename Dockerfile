FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project --no-cache \
    && useradd --uid 10001 --create-home bizbot

COPY main.py ./
COPY lib/ ./lib/
COPY services/ ./services/

USER bizbot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import json, sys, urllib.request; sys.exit(not json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)).get('bot_connected', False))"]
CMD ["python", "main.py"]
