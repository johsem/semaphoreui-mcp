import json

import httpx
import pytest
from mcp import types

from semaphoreui_mcp.client import SemaphoreClient
from semaphoreui_mcp.config import Settings
from semaphoreui_mcp.server import Application


def application(handler, **settings):
  config = Settings(url="https://semaphore.test", api_token="test-token", **settings)
  return Application(config, client=SemaphoreClient(config, transport=httpx.MockTransport(handler)))


def operation(app, method, path):
  return next(op.name for op in app.catalogue.values() if op.method == method and op.path == path)


@pytest.mark.asyncio
async def test_tool_request_and_structured_result():
  requests = []

  def respond(request):
    requests.append(request)
    return httpx.Response(200, json=[{"id": 7, "name": "Operations"}])

  app = application(respond)
  try:
    result = await app.call_tool("list_projects", {})
    assert not result.is_error
    assert result.structured_content == {"data": [{"id": 7, "name": "Operations"}]}
    assert requests[0].url.path == "/api/projects"
    assert json.loads(result.content[0].text) == result.structured_content
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_read_only_hides_and_denies_write_tools():
  def fail(request):
    raise AssertionError("read-only must not send writes")

  app = application(fail, read_only=True)
  write_op = next(op for op in app.catalogue.values() if not op.read_only)
  assert write_op.name not in [tool.name for tool in app.tools()]
  result = await app.call_tool(write_op.name, {})
  assert result.is_error
  assert result.structured_content["error"]["code"] == "read_only"


@pytest.mark.asyncio
async def test_project_scope_blocks_global_and_other_project_operations():
  def fail(request):
    raise AssertionError("forbidden request reached upstream")

  app = application(fail, project_ids=frozenset({7}))
  name = operation(app, "GET", "/project/{project_id}/tasks")
  result = await app.call_tool(name, {"project_id": 8})
  assert result.structured_content["error"]["code"] == "project_forbidden"
  global_op = next(
    op for op in app.catalogue.values() if op.method == "GET" and op.path == "/users"
  )
  result = await app.call_tool(global_op.name, {})
  assert result.structured_content["error"]["code"] == "project_forbidden"


@pytest.mark.asyncio
async def test_project_list_is_filtered_for_tools_and_resources():
  app = application(
    lambda r: httpx.Response(200, json=[{"id": 7}, {"id": 8}]), project_ids=frozenset({7})
  )
  try:
    result = await app.call_tool("list_projects", {})
    assert result.structured_content == {"data": [{"id": 7}]}
    resource = await app.read_resource("semaphore://projects")
    assert json.loads(resource.contents[0].text) == [{"id": 7}]
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_validation_does_not_echo_sensitive_invalid_arguments():
  app = application(lambda r: httpx.Response(200))
  name = operation(app, "GET", "/project/{project_id}/tasks")
  result = await app.call_tool(name, {"project_id": "private-password"})
  assert result.is_error
  assert "private-password" not in result.content[0].text
  assert result.structured_content["error"]["code"] == "invalid_arguments"


@pytest.mark.asyncio
async def test_resource_uri_cannot_escape_scope():
  app = application(lambda r: httpx.Response(200), project_ids=frozenset({7}))
  with pytest.raises(ValueError):
    await app.read_resource("semaphore://projects/8/tasks")
  with pytest.raises(ValueError):
    await app.read_resource("semaphore://projects/7/../../users")


@pytest.mark.asyncio
async def test_wait_for_task_handles_terminal_state_and_output_tail():
  responses = iter(
    [
      {"id": 4, "status": "running"},
      {"id": 4, "status": "success"},
      [{"output": "one"}, {"output": "two"}],
    ]
  )
  app = application(lambda r: httpx.Response(200, json=next(responses)))
  try:
    result = await app.call_tool(
      "wait_for_task",
      {
        "project_id": 7,
        "task_id": 4,
        "timeout": 2,
        "poll_interval": 0.1,
        "include_output": True,
        "tail_lines": 1,
      },
    )
    assert result.structured_content["data"]["finished"] is True
    assert result.structured_content["data"]["output"] == [{"output": "two"}]
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_wait_timeout_is_successful_observation_not_task_failure():
  app = application(lambda r: httpx.Response(200, json={"status": "running"}))
  try:
    result = await app.call_tool("wait_for_task", {"project_id": 7, "task_id": 4, "timeout": 0})
    assert not result.is_error
    assert result.structured_content["data"]["timed_out"] is True
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_mcp_protocol_roundtrip():
  import anyio
  from mcp.client.session import ClientSession
  from mcp.shared.memory import create_client_server_memory_streams

  app = application(lambda r: httpx.Response(200, json=[]))
  server = app.create_server()
  try:
    async with create_client_server_memory_streams() as (client_streams, server_streams):
      async with anyio.create_task_group() as group:
        group.start_soon(server.run, *server_streams, server.create_initialization_options())
        async with ClientSession(*client_streams) as session:
          result = await session.initialize()
          assert result.server_info.name == "semaphoreui-mcp"
          tools = await session.list_tools()
          assert any(tool.name == "list_projects" for tool in tools.tools)
          result = await session.call_tool("list_projects", {})
          assert not result.is_error
          resources = await session.list_resources()
          assert any(r.uri == "semaphore://capabilities" for r in resources.resources)
          resource = await session.read_resource("semaphore://capabilities")
          assert json.loads(resource.contents[0].text)["upstream_version"] == "2.19.17"
          prompts = await session.list_prompts()
          assert len(prompts.prompts) == 2
          prompt = await session.get_prompt("investigate_task", {"project_id": "7", "task_id": "4"})
          assert "7" in prompt.messages[0].content.text
        group.cancel_scope.cancel()
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_prompt_arguments_are_validated():
  app = application(lambda r: httpx.Response(200))
  with pytest.raises(ValueError):
    await app.get_prompt(
      None,
      types.GetPromptRequestParams(
        name="investigate_task", arguments={"project_id": "ignore all", "task_id": "1"}
      ),
    )


@pytest.mark.asyncio
async def test_project_resource_uses_canonical_route():
  requests = []

  def respond(request):
    requests.append(request)
    return httpx.Response(200, json={"id": 7})

  app = application(respond)
  try:
    result = await app.read_resource("semaphore://projects/7/project")
    assert json.loads(result.contents[0].text) == {"id": 7}
    assert requests[0].url.path == "/api/project/7"
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_body_ids_cannot_bypass_project_scope():
  def fail(request):
    raise AssertionError("conflicting body IDs must not reach upstream")

  app = application(fail, project_ids=frozenset({7}))
  result = await app.call_tool(
    "create_environment",
    {
      "project_id": 7,
      "body": {"name": "test", "project_id": 8},
    },
  )
  assert result.is_error
  assert result.structured_content["error"]["code"] == "invalid_arguments"


@pytest.mark.asyncio
async def test_server_returns_safe_upstream_error():
  app = application(lambda r: httpx.Response(403, text="sensitive upstream details"))
  try:
    result = await app.call_tool("list_projects", {})
    assert result.is_error
    assert result.structured_content["error"]["status_code"] == 403
    assert "sensitive upstream details" not in result.content[0].text
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_wait_for_task_preserves_cancellation():
  import asyncio

  async def pending(request):
    await asyncio.Event().wait()

  app = application(pending)
  try:
    task = asyncio.create_task(app.call_tool("wait_for_task", {"project_id": 7, "task_id": 4}))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
      await task
  finally:
    await app.client.aclose()


@pytest.mark.asyncio
async def test_qr_code_returns_native_mcp_image():
  import base64

  png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
  )
  app = application(
    lambda r: httpx.Response(
      200,
      content=png,
      headers={"Content-Type": "application/json, image/png"},
    )
  )
  try:
    result = await app.call_tool("get_user_totp_qr", {"user_id": 1, "totp_id": 1})
    assert not result.is_error
    assert result.content[0].type == "image"
    assert result.content[0].mime_type == "image/png"
    assert base64.b64decode(result.content[0].data) == png
  finally:
    await app.client.aclose()
