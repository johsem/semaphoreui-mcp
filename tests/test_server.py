import json

import httpx
import pytest
from mcp import types

from semaphoreui_mcp.client import SemaphoreClient
from semaphoreui_mcp.config import Settings
from semaphoreui_mcp.profiles import CORE_TOOLS
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


@pytest.mark.asyncio
async def test_core_profile_excludes_and_denies_every_non_core_tool():
  requests = []
  app = application(
    lambda request: requests.append(request) or httpx.Response(200), tool_profile="core"
  )
  async with app.client:
    names = {tool.name for tool in app.tools()}
    assert names == CORE_TOOLS
    assert CORE_TOOLS <= app.catalogue.keys() | {"wait_for_task"}
    assert {
      name for name in names if name != "wait_for_task" and not app.catalogue[name].read_only
    } == {
      "create_task",
      "stop_task",
    }
    for name in app.catalogue.keys() - CORE_TOOLS:
      result = await app.call_tool(name, {})
      assert result.is_error
      assert result.structured_content["error"]["code"] == "tool_disabled"
    assert not requests
    assert app.capabilities()["tool_profile"] == "core"


@pytest.mark.asyncio
async def test_full_profile_keeps_complete_catalogue():
  app = application(lambda request: httpx.Response(200))
  async with app.client:
    assert {tool.name for tool in app.tools()} == app.catalogue.keys() | {"wait_for_task"}


@pytest.mark.asyncio
async def test_core_profile_composes_with_read_only_and_project_restrictions():
  requests = []
  app = application(
    lambda request: requests.append(request) or httpx.Response(200, json=[{"id": 7}, {"id": 8}]),
    tool_profile="core",
    read_only=True,
    project_ids=frozenset({7}),
  )
  async with app.client:
    names = {tool.name for tool in app.tools()}
    assert "create_task" not in names
    assert "stop_task" not in names
    for name in ("create_task", "stop_task"):
      result = await app.call_tool(name, {})
      assert result.structured_content["error"]["code"] == "read_only"
    for name, arguments in {
      "get_template": {"project_id": 8, "template_id": 2},
      "wait_for_task": {"project_id": 8, "task_id": 4},
    }.items():
      result = await app.call_tool(name, arguments)
      assert result.structured_content["error"]["code"] == "project_forbidden"
    assert not requests
    result = await app.call_tool("list_projects", {})
    assert result.structured_content["data"] == [{"id": 7}]
    with pytest.raises(ValueError, match="outside"):
      await app.read_resource("semaphore://projects/8/tasks")
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_core_profile_preserves_all_resources_and_prompts():
  app = application(
    lambda request: httpx.Response(200, json={"path": request.url.path}), tool_profile="core"
  )
  async with app.client:
    for collection, suffix in {
      "project": "",
      "templates": "/templates",
      "tasks": "/tasks",
      "inventory": "/inventory",
      "repositories": "/repositories",
      "environments": "/environment",
      "schedules": "/schedules",
      "tasks/4": "/tasks/4",
    }.items():
      result = await app.read_resource(f"semaphore://projects/7/{collection}")
      assert json.loads(result.contents[0].text) == {"path": f"/api/project/7{suffix}"}
    for prompt, identifier in {
      "investigate_task": "task_id",
      "plan_template_run": "template_id",
    }.items():
      result = await app.get_prompt(
        None,
        types.GetPromptRequestParams(name=prompt, arguments={"project_id": "7", identifier: "4"}),
      )
      assert "project 7" in result.messages[0].content.text


@pytest.mark.asyncio
async def test_core_profile_inspect_launch_cancel_and_read_logs():
  requests = []

  def respond(request):
    requests.append(request)
    match request.method, request.url.path:
      case "GET", "/api/project/7/templates":
        return httpx.Response(200, json=[{"id": 2, "name": "Deploy"}])
      case "POST", "/api/project/7/tasks":
        assert json.loads(request.content) == {"template_id": 2, "params": {"dry_run": True}}
        return httpx.Response(201, json={"id": 4, "status": "waiting"})
      case "POST", "/api/project/7/tasks/4/stop":
        assert json.loads(request.content) == {}
        return httpx.Response(204)
      case "GET", "/api/project/7/tasks/4":
        return httpx.Response(200, json={"id": 4, "status": "stopped"})
      case "GET", "/api/project/7/tasks/4/output":
        return httpx.Response(200, json=[{"output": "Cancelled"}])
    raise AssertionError(f"Unexpected request: {request.method} {request.url.path}")

  app = application(respond, tool_profile="core", project_ids=frozenset({7}))
  async with app.client:
    result = await app.call_tool("list_templates", {"project_id": 7})
    template = result.structured_content["data"][0]
    result = await app.call_tool(
      "create_task",
      {"project_id": 7, "body": {"template_id": template["id"], "params": {"dry_run": True}}},
    )
    task_id = result.structured_content["data"]["id"]
    result = await app.call_tool("stop_task", {"project_id": 7, "task_id": task_id})
    assert not result.is_error
    result = await app.call_tool(
      "wait_for_task", {"project_id": 7, "task_id": task_id, "include_output": True}
    )
    assert result.structured_content["data"]["finished"] is True
    assert result.structured_content["data"]["output"] == [{"output": "Cancelled"}]
    assert len(requests) == 5
