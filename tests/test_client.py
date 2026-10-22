import asyncio
import base64
import json

import httpx
import pytest

from semaphoreui_mcp.client import SemaphoreClient, SemaphoreError
from semaphoreui_mcp.config import Settings


def token_settings(**overrides):
  return Settings(
    url="https://semaphore.example/reverse-proxy",
    api_token="configured-api-token",
    **overrides,
  )


def session_settings():
  return Settings(
    url="https://semaphore.example",
    username="admin",
    password="configured-password",
  )


@pytest.fixture
def retry_delays(monkeypatch):
  delays = []

  async def record_sleep(delay):
    delays.append(delay)

  monkeypatch.setattr("semaphoreui_mcp.client.asyncio.sleep", record_sleep)
  return delays


@pytest.mark.asyncio
async def test_bearer_auth_reverse_proxy_and_query_encoding():
  requests = []

  def handler(request):
    requests.append(request)
    return httpx.Response(200, json=[{"id": 1}])

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    result = await client.request("GET", "/project/1/tasks", params={"sort": "a&b"})
  assert result == [{"id": 1}]
  assert len(requests) == 1
  assert requests[0].url.path == "/reverse-proxy/api/project/1/tasks"
  assert requests[0].url.params["sort"] == "a&b"
  assert requests[0].headers["Authorization"] == "Bearer configured-api-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
  ("response", "expected"),
  [
    (httpx.Response(204), {"success": True}),
    (httpx.Response(200, text="task output\nline 2"), "task output\nline 2"),
    (httpx.Response(200, json={"id": 2}), {"id": 2}),
  ],
)
async def test_response_formats(response, expected):
  async with SemaphoreClient(
    token_settings(), httpx.MockTransport(lambda request: response)
  ) as client:
    assert await client.request("GET", "/ping") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
  "content_type", ["image/png", "application/json, image/png", "application/octet-stream"]
)
async def test_binary_responses_are_lossless(content_type):
  data = b"\x89PNG\r\n\x1a\n\x00\xff"
  response = httpx.Response(200, content=data, headers={"Content-Type": content_type})
  async with SemaphoreClient(
    token_settings(), httpx.MockTransport(lambda request: response)
  ) as client:
    result = await client.request("GET", "/users/1/totp/qr")
  expected_type = "image/png" if "image/png" in content_type else content_type
  assert result["content_type"] == expected_type
  assert base64.b64decode(result["data_base64"]) == data


@pytest.mark.asyncio
@pytest.mark.parametrize(
  "path",
  [
    "https://attacker.example/steal",
    "//attacker.example/steal",
    "/../users",
    "/project/1/../../users",
    "/project/%2e%2e/users",
    "/project/%252e%252e/users",
    "/%2f%2fattacker.example",
    "/project/1\\users",
    "/project/1?override=2",
    "/project/1#fragment",
    "/project/%3fsecret",
    "/project/\n1",
    "/",
    "",
  ],
)
async def test_unsafe_paths_never_make_a_request(path):
  def handler(request):
    pytest.fail("Unsafe paths must fail before authenticating or sending requests")

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", path)
  assert error.value.code == "invalid_path"


@pytest.mark.asyncio
async def test_redirect_is_refused_without_leaking_credentials():
  requests = []

  def handler(request):
    requests.append(request)
    return httpx.Response(
      302,
      headers={"Location": "https://attacker.example"},
      text="configured-api-token",
    )

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", "/projects")
  assert len(requests) == 1
  assert error.value.code == "redirect_refused"
  assert "configured-api-token" not in str(error.value)


@pytest.mark.asyncio
async def test_session_login_is_lazy_and_shared_by_concurrent_requests():
  login_requests = []
  api_requests = []

  async def handler(request):
    if request.url.path == "/api/auth/login":
      login_requests.append(request)
      await asyncio.sleep(0)
      return httpx.Response(204, headers={"Set-Cookie": "semaphore=session-value; Path=/api"})
    api_requests.append(request)
    return httpx.Response(200, json=[])

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    assert not login_requests
    await asyncio.gather(*[client.request("GET", "/projects") for _ in range(5)])
  assert len(login_requests) == 1
  assert json.loads(login_requests[0].content) == {
    "auth": "admin",
    "password": "configured-password",
  }
  assert len(api_requests) == 5
  assert all(request.headers["Cookie"] == "semaphore=session-value" for request in api_requests)
  assert all("Authorization" not in request.headers for request in api_requests)


@pytest.mark.asyncio
async def test_expired_session_get_is_reauthenticated_once():
  login_count = 0
  api_count = 0

  def handler(request):
    nonlocal login_count, api_count
    if request.url.path == "/api/auth/login":
      login_count += 1
      return httpx.Response(204, headers={"Set-Cookie": f"session={login_count}; Path=/"})
    api_count += 1
    if api_count == 1:
      return httpx.Response(401)
    assert request.headers["Cookie"] == "session=2"
    return httpx.Response(200, json={"id": 1})

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    assert await client.request("GET", "/project/1/") == {"id": 1}
  assert login_count == 2
  assert api_count == 2


@pytest.mark.asyncio
async def test_concurrent_expired_sessions_share_one_refresh():
  login_count = 0
  expired_count = 0
  both_expired = asyncio.Event()

  async def handler(request):
    nonlocal login_count, expired_count
    if request.url.path == "/api/auth/login":
      login_count += 1
      return httpx.Response(204, headers={"Set-Cookie": f"session={login_count}; Path=/"})
    if request.headers.get("Cookie") == "session=1":
      expired_count += 1
      if expired_count == 2:
        both_expired.set()
      await both_expired.wait()
      return httpx.Response(401)
    return httpx.Response(200, json=[])

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    await asyncio.wait_for(
      asyncio.gather(client.request("GET", "/projects"), client.request("GET", "/projects")),
      timeout=2,
    )
  assert login_count == 2


@pytest.mark.asyncio
async def test_persistent_auth_failure_has_bounded_refresh():
  requests = []

  def handler(request):
    requests.append(request)
    if request.url.path == "/api/auth/login":
      return httpx.Response(204, headers={"Set-Cookie": "session=value; Path=/"})
    return httpx.Response(401, text="configured-password")

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", "/projects")
  assert len(requests) == 4
  assert error.value.code == "authentication_failed"
  assert "configured-password" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 503])
async def test_writes_are_never_retried_even_for_expired_sessions(status):
  writes = []
  login_count = 0

  def handler(request):
    nonlocal login_count
    if request.url.path == "/api/auth/login":
      login_count += 1
      return httpx.Response(204, headers={"Set-Cookie": "session=value; Path=/"})
    writes.append(request)
    return httpx.Response(status)

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("POST", "/project/1/tasks", json={"template_id": 5})
  assert len(writes) == 1
  assert login_count == 1
  assert error.value.retryable is False
  assert json.loads(writes[0].content) == {"template_id": 5}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_transient_gets_retry_twice_with_capped_retry_after(status, retry_delays):
  requests = []

  def handler(request):
    requests.append(request)
    if len(requests) < 3:
      return httpx.Response(status, headers={"Retry-After": "3600"})
    return httpx.Response(200, json=[])

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    assert await client.request("GET", "/projects") == []
  assert len(requests) == 3
  assert retry_delays == [5.0, 5.0]


@pytest.mark.asyncio
async def test_transient_get_failure_is_bounded_and_safe(retry_delays):
  requests = []

  def handler(request):
    requests.append(request)
    raise httpx.ConnectError("Failure with configured-api-token", request=request)

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", "/projects")
  assert len(requests) == 3
  assert retry_delays == [0.25, 0.5]
  assert error.value.retryable is True
  assert error.value.code == "connection_error"
  assert "configured-api-token" not in str(error.value)


@pytest.mark.asyncio
async def test_transient_http_failure_is_bounded(retry_delays):
  requests = []

  def handler(request):
    requests.append(request)
    return httpx.Response(503)

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", "/projects")
  assert len(requests) == 3
  assert retry_delays == [0.25, 0.5]
  assert error.value.status_code == 503
  assert error.value.retryable is True


@pytest.mark.asyncio
async def test_invalid_bearer_token_is_not_retried(retry_delays):
  requests = []

  def handler(request):
    requests.append(request)
    return httpx.Response(401)

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", "/projects")
  assert len(requests) == 1
  assert retry_delays == []
  assert error.value.code == "authentication_failed"


@pytest.mark.asyncio
async def test_write_timeout_is_not_retried(retry_delays):
  requests = []

  def handler(request):
    requests.append(request)
    raise httpx.ReadTimeout("Request may already have succeeded", request=request)

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("POST", "/project/1/tasks", json={"template_id": 5})
  assert len(requests) == 1
  assert retry_delays == []
  assert error.value.retryable is False


@pytest.mark.asyncio
async def test_get_http_error_does_not_expose_response_body_or_retry(retry_delays):
  requests = []

  def handler(request):
    requests.append(request)
    return httpx.Response(403, text="configured-api-token and other-server-secret")

  async with SemaphoreClient(token_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError) as error:
      await client.request("GET", "/projects")
  assert len(requests) == 1
  assert error.value.status_code == 403
  assert error.value.code == "forbidden"
  assert "secret" not in str(error.value)
  assert "configured-api-token" not in str(error.value)
  assert retry_delays == []


@pytest.mark.asyncio
async def test_configured_credentials_redacted_without_removing_requested_secrets():
  response = {
    "token": "newly-created-user-requested-token",
    "password": "requested-key-password",
    "output": ["echo configured-api-token", "ordinary task output"],
  }
  async with SemaphoreClient(
    token_settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=response))
  ) as client:
    result = await client.request("GET", "/user/tokens")
  assert result["token"] == "newly-created-user-requested-token"
  assert result["password"] == "requested-key-password"
  assert result["output"] == ["echo [REDACTED]", "ordinary task output"]


@pytest.mark.asyncio
async def test_login_requires_session_cookie():
  async with SemaphoreClient(
    session_settings(), httpx.MockTransport(lambda request: httpx.Response(204))
  ) as client:
    with pytest.raises(SemaphoreError, match="did not establish a session"):
      await client.request("GET", "/projects")


@pytest.mark.asyncio
async def test_refresh_cannot_reuse_an_expired_cookie():
  login_count = 0

  def handler(request):
    nonlocal login_count
    if request.url.path == "/api/auth/login":
      login_count += 1
      if login_count == 1:
        return httpx.Response(204, headers={"Set-Cookie": "session=old; Path=/"})
      return httpx.Response(204)
    return httpx.Response(401)

  async with SemaphoreClient(session_settings(), httpx.MockTransport(handler)) as client:
    with pytest.raises(SemaphoreError, match="did not establish a session"):
      await client.request("GET", "/projects")
  assert login_count == 2


def test_missing_custom_ca_fails_with_safe_configuration_message():
  with pytest.raises(ValueError, match="SEMAPHORE_CA_BUNDLE"):
    SemaphoreClient(token_settings(ca_bundle="/nonexistent/private-ca.pem"))
