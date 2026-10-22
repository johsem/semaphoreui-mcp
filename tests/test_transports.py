import json
import os
import sys

import httpx
import pytest

from semaphoreui_mcp.__main__ import create_http_app
from semaphoreui_mcp.client import SemaphoreClient
from semaphoreui_mcp.config import Settings
from semaphoreui_mcp.profiles import CORE_TOOLS
from semaphoreui_mcp.server import Application


def application(**options):
  settings = Settings(url="https://semaphore.test", api_token="test-token", **options)
  client = SemaphoreClient(
    settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
  )
  return Application(settings, client=client)


def test_network_listener_requires_token():
  with pytest.raises(ValueError, match="MCP_HTTP_TOKEN"):
    create_http_app(application(), host="0.0.0.0")


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["full", "core"])
async def test_http_auth_initialization_and_tool_execution(profile):
  app = create_http_app(application(tool_profile=profile), token="mcp-secret")
  async with app.router.lifespan_context(app):
    async with httpx.AsyncClient(
      transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
      payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
          "protocolVersion": "2025-06-18",
          "capabilities": {},
          "clientInfo": {"name": "pytest", "version": "1"},
        },
      }
      denied = await client.post("/mcp", json=payload)
      assert denied.status_code == 401
      headers = {
        "Authorization": "Bearer mcp-secret",
        "Accept": "application/json, text/event-stream",
      }
      result = await client.post("/mcp", headers=headers, json=payload)
      assert result.status_code == 200, result.text
      assert result.json()["result"]["serverInfo"]["name"] == "semaphoreui-mcp"
      headers["MCP-Protocol-Version"] = "2025-06-18"
      result = await client.post(
        "/mcp",
        headers=headers,
        json={
          "jsonrpc": "2.0",
          "id": 2,
          "method": "tools/call",
          "params": {"name": "list_projects", "arguments": {}},
        },
      )
      assert result.status_code == 200, result.text
      assert result.json()["result"]["structuredContent"] == {"data": []}
      listed = await client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
      )
      names = {tool["name"] for tool in listed.json()["result"]["tools"]}
      if profile == "core":
        assert names == CORE_TOOLS
        excluded = await client.post(
          "/mcp",
          headers=headers,
          json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "create_project", "arguments": {"body": {"name": "Denied"}}},
          },
        )
        assert excluded.json()["result"]["structuredContent"]["error"]["code"] == "tool_disabled"
      else:
        assert "create_project" in names
      denied = await client.post(
        "/mcp", headers={**headers, "Host": "attacker.example"}, json=payload
      )
      assert denied.status_code == 421


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["full", "core"])
async def test_stdio_subprocess_initialization_and_offline_resources(profile):
  from mcp.client.session import ClientSession
  from mcp.client.stdio import StdioServerParameters, stdio_client

  params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "semaphoreui_mcp"],
    env={
      **os.environ,
      "SEMAPHORE_URL": "https://semaphore.test",
      "SEMAPHORE_API_TOKEN": "test-token",
      "SEMAPHORE_TOOL_PROFILE": profile,
      "PYTHONPATH": "src",
    },
  )
  async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
      await session.initialize()
      listed = await session.list_tools()
      assert any(tool.name == "wait_for_task" for tool in listed.tools)
      if profile == "core":
        assert {tool.name for tool in listed.tools} == CORE_TOOLS
        excluded = await session.call_tool("list_users", {})
        assert excluded.structured_content["error"]["code"] == "tool_disabled"
      resource = await session.read_resource("semaphore://capabilities")
      assert json.loads(resource.contents[0].text)["upstream_version"] == "2.19.17"
      assert json.loads(resource.contents[0].text)["tool_profile"] == profile
      invalid = await session.call_tool("wait_for_task", {"project_id": 1})
      assert invalid.is_error
