FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/johsem/semaphoreui-mcp" \
    org.opencontainers.image.description="Model Context Protocol server for Semaphore UI" \
    org.opencontainers.image.licenses="MIT"

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable \
    && useradd --uid 10001 --create-home mcp

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["semaphoreui-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
