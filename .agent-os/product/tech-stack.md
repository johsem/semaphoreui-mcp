# Technical stack

- Python 3.13+, following the user's global Python and two-space style preferences.
- Official `mcp` Python SDK 2.x for protocol types, server lifecycle, stdio, and
  Streamable HTTP. Its ASGI support replaces a separate FastAPI layer for this
  protocol service.
- `httpx` for asynchronous Semaphore requests and session cookies.
- `PyYAML` for the bundled upstream API source; `jsonschema` for tool arguments.
- `starlette` for HTTP middleware responses and `uvicorn` for the ASGI host.
- Setuptools with a `src/` package layout; package data contains the API catalogue,
  upstream schema, and license attribution.
- `uv.lock` for reproducible runtime and development dependencies.
- pytest, pytest-asyncio, pytest-cov, and Ruff for verification.
- Docker for self-hosting; GitHub Actions and GitLab CI for validation and
  distribution artifacts.

No database is required. Semaphore owns persistent configuration and execution
state. The MCP service maintains only the HTTP authentication/client state needed
to access Semaphore; HTTP MCP sessions are stateless.
