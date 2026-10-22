"""Executable stdio and Streamable HTTP transports."""

import argparse
import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

from semaphoreui_mcp import __version__
from semaphoreui_mcp.catalogue import load_catalogue
from semaphoreui_mcp.config import Settings
from semaphoreui_mcp.server import Application

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class BearerTokenMiddleware:
  def __init__(self, app, token):
    self.app = app
    self.expected = f"Bearer {token}".encode()

  async def __call__(self, scope, receive, send):
    if scope["type"] == "http":
      headers = dict(scope["headers"])
      if not hmac.compare_digest(headers.get(b"authorization", b""), self.expected):
        response = JSONResponse(
          {"error": "Unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
        )
        await response(scope, receive, send)
        return
    await self.app(scope, receive, send)


def create_http_app(
  application: Application,
  *,
  host="127.0.0.1",
  token=None,
  allowed_hosts=None,
  allowed_origins=None,
):
  if host not in LOOPBACK_HOSTS and not token:
    raise ValueError("MCP_HTTP_TOKEN is required when HTTP listens beyond loopback.")
  hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
  if host not in {"0.0.0.0", "::"} and host not in LOOPBACK_HOSTS:
    hosts.append(f"{host}:*")
  security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=allowed_hosts or hosts,
    allowed_origins=allowed_origins
    or ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
  )
  app = application.create_server().streamable_http_app(
    stateless_http=True,
    json_response=True,
    transport_security=security,
    host=host,
  )
  sdk_lifespan = app.router.lifespan_context

  @asynccontextmanager
  async def lifespan(app):
    async with application.client, sdk_lifespan(app):
      yield

  app.router.lifespan_context = lifespan
  if token:
    app.add_middleware(BearerTokenMiddleware, token=token)
  return app


async def run_stdio(application):
  server = application.create_server()
  async with application.client, stdio_server() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, server.create_initialization_options())


def comma_values(name):
  return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()] or None


def main():
  parser = argparse.ArgumentParser(description="Semaphore UI MCP server")
  parser.add_argument("--version", action="version", version=__version__)
  parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
  parser.add_argument("--host", default="127.0.0.1")
  parser.add_argument("--port", type=int, default=8000)
  parser.add_argument(
    "--list-tools",
    action="store_true",
    help="Print the bundled API tool catalogue as JSON without connecting",
  )
  args = parser.parse_args()
  logging.basicConfig(level=logging.WARNING)
  if args.list_tools:
    tools = [
      {"name": op.name, "method": op.method, "path": op.path, "description": op.description}
      for op in load_catalogue().values()
    ]
    tools.append(
      {"name": "wait_for_task", "description": "Poll task status with an optional output tail."}
    )
    print(json.dumps(tools, indent=2))
    return
  if not 1 <= args.port <= 65535:
    parser.error("--port must be between 1 and 65535")
  try:
    application = Application(Settings.from_env())
    if args.transport == "stdio":
      asyncio.run(run_stdio(application))
    else:
      app = create_http_app(
        application,
        host=args.host,
        token=os.environ.get("MCP_HTTP_TOKEN") or None,
        allowed_hosts=comma_values("MCP_ALLOWED_HOSTS"),
        allowed_origins=comma_values("MCP_ALLOWED_ORIGINS"),
      )
      uvicorn.run(app, host=args.host, port=args.port, log_level="warning", access_log=False)
  except (ValueError, OSError) as exc:
    parser.error(str(exc))
  except KeyboardInterrupt:
    pass


if __name__ == "__main__":
  main()
