"""Asynchronous Semaphore HTTP client with bounded, read-only retries."""

import asyncio
import base64
import ssl
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from semaphoreui_mcp.config import Settings

_TRANSIENT_STATUSES = {429, 502, 503, 504}
_MAX_RETRIES = 2
_MAX_RETRY_DELAY = 5.0


class SemaphoreError(Exception):
  """A safe error suitable for returning to an MCP caller."""

  def __init__(
    self,
    message: str,
    *,
    code: str,
    status_code: int | None = None,
    retryable: bool = False,
  ) -> None:
    super().__init__(message)
    self.message = message
    self.code = code
    self.status_code = status_code
    self.retryable = retryable


def _relative_path(path: str) -> str:
  invalid = not isinstance(path, str) or not path or path.startswith("//")
  if not invalid:
    parsed = urlsplit(path)
    invalid = bool(parsed.scheme or parsed.netloc or parsed.query or parsed.fragment)
  if invalid:
    raise SemaphoreError("Only relative Semaphore API paths are allowed", code="invalid_path")
  decoded = path
  for _ in range(8):
    next_value = unquote(decoded)
    if next_value == decoded:
      break
    decoded = next_value
  if (
    "\\" in decoded
    or "?" in decoded
    or "#" in decoded
    or decoded.startswith("//")
    or any(ord(character) < 32 or character.isspace() for character in decoded)
    or any(part in {".", ".."} for part in decoded.split("/"))
    or "%" in decoded
  ):
    raise SemaphoreError("The API path contains unsafe characters", code="invalid_path")
  relative = path.removeprefix("/")
  if not relative:
    raise SemaphoreError("An API endpoint path is required", code="invalid_path")
  return relative


class SemaphoreClient:
  def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
    self.settings = settings
    verify: bool | ssl.SSLContext = settings.verify_tls
    if settings.ca_bundle:
      try:
        verify = ssl.create_default_context(cafile=settings.ca_bundle)
      except (OSError, ssl.SSLError):
        raise ValueError(
          "SEMAPHORE_CA_BUNDLE must point to a readable CA certificate bundle"
        ) from None
    headers = {"Accept": "application/json", "User-Agent": "semaphoreui-mcp"}
    if settings.api_token:
      headers["Authorization"] = f"Bearer {settings.api_token}"
    self._client = httpx.AsyncClient(
      base_url=settings.url,
      headers=headers,
      timeout=settings.timeout,
      verify=verify,
      follow_redirects=False,
      transport=transport,
    )
    self._login_lock = asyncio.Lock()
    self._session_generation = 0
    self._authenticated = False

  async def __aenter__(self) -> "SemaphoreClient":
    return self

  async def __aexit__(self, *args: object) -> None:
    await self.aclose()

  async def aclose(self) -> None:
    await self._client.aclose()

  async def _login(self, expired_generation: int | None = None) -> None:
    if self.settings.api_token:
      return
    async with self._login_lock:
      if expired_generation is None and self._authenticated:
        return
      if (
        expired_generation is not None
        and expired_generation != self._session_generation
        and self._authenticated
      ):
        return
      self._authenticated = False
      self._client.cookies.clear()
      response = await self._send(
        "POST",
        "auth/login",
        json={"auth": self.settings.username, "password": self.settings.password},
      )
      self._raise_for_status(response, "POST")
      if not self._client.cookies:
        raise SemaphoreError(
          "Semaphore login did not establish a session", code="authentication_failed"
        )
      self._session_generation += 1
      self._authenticated = True

  async def request(
    self,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    json: Any = None,
  ) -> Any:
    relative = _relative_path(path)
    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
      raise SemaphoreError("Unsupported HTTP method", code="invalid_method")
    await self._login()
    generation = self._session_generation
    response = await self._send(method, relative, params=params, json=json)
    # A GET can be repeated safely after another request has refreshed the session.
    if response.status_code == 401 and method == "GET" and not self.settings.api_token:
      await self._login(expired_generation=generation)
      response = await self._send(method, relative, params=params, json=json)
    self._raise_for_status(response, method)
    if not response.content:
      return {"success": True}
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    # The TOTP QR handler declares "application/json, image/png" upstream.
    if "image/" in content_type:
      content_type = next(part.strip() for part in content_type.split(",") if "image/" in part)
    if content_type and not (
      content_type.startswith("text/")
      or content_type == "application/json"
      or content_type.endswith("+json")
    ):
      return {
        "content_type": content_type,
        "data_base64": base64.b64encode(response.content).decode("ascii"),
      }
    try:
      result = response.json()
    except ValueError:
      result = response.text
    return self._redact_credentials(result)

  async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
    for attempt in range(_MAX_RETRIES + 1):
      try:
        response = await self._client.request(method, path, **kwargs)
      except (httpx.TimeoutException, httpx.NetworkError):
        if method == "GET" and attempt < _MAX_RETRIES:
          await asyncio.sleep(0.25 * (2**attempt))
          continue
        raise SemaphoreError(
          "Unable to reach Semaphore; check the server URL, TLS, and network connection",
          code="connection_error",
          retryable=method == "GET",
        ) from None
      except httpx.HTTPError:
        raise SemaphoreError(
          "Semaphore returned an invalid HTTP response", code="http_error"
        ) from None
      if method == "GET" and response.status_code in _TRANSIENT_STATUSES and attempt < _MAX_RETRIES:
        await asyncio.sleep(self._retry_delay(response, attempt))
        continue
      return response
    raise AssertionError("Retry loop did not return")

  @staticmethod
  def _retry_delay(response: httpx.Response, attempt: int) -> float:
    fallback = 0.25 * (2**attempt)
    header = response.headers.get("Retry-After")
    if header is None:
      return fallback
    try:
      delay = float(header)
    except ValueError:
      try:
        retry_at = parsedate_to_datetime(header)
        if retry_at.tzinfo is None:
          retry_at = retry_at.replace(tzinfo=UTC)
        delay = (retry_at - datetime.now(UTC)).total_seconds()
      except (ValueError, TypeError, OverflowError):
        return fallback
    return max(0.0, min(delay, _MAX_RETRY_DELAY))

  @staticmethod
  def _raise_for_status(response: httpx.Response, method: str) -> None:
    status = response.status_code
    if 200 <= status < 300:
      return
    if 300 <= status < 400:
      code, message = "redirect_refused", "Semaphore redirected the request; verify SEMAPHORE_URL"
    elif status == 401:
      code, message = "authentication_failed", "Semaphore authentication failed"
    elif status == 403:
      code, message = "forbidden", "The Semaphore account cannot perform this operation"
    elif status == 404:
      code, message = "not_found", "The Semaphore resource or API endpoint was not found"
    elif status == 409:
      code, message = "conflict", "The operation conflicts with the current Semaphore state"
    elif status == 429:
      code, message = "rate_limited", "Semaphore rate-limited the request"
    elif status >= 500:
      code, message = "upstream_error", "Semaphore encountered a server error"
    else:
      code, message = "request_rejected", "Semaphore rejected the request; check its parameters"
    raise SemaphoreError(
      message,
      code=code,
      status_code=status,
      retryable=method == "GET" and status in _TRANSIENT_STATUSES,
    )

  def _redact_credentials(self, value: Any) -> Any:
    if isinstance(value, str):
      for secret in (self.settings.api_token, self.settings.password):
        if secret:
          value = value.replace(secret, "[REDACTED]")
      return value
    if isinstance(value, list):
      return [self._redact_credentials(item) for item in value]
    if isinstance(value, dict):
      return {
        self._redact_credentials(key): self._redact_credentials(item) for key, item in value.items()
      }
    return value
