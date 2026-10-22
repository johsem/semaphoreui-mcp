"""Validated runtime settings sourced from the process environment."""

import math
import os
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit, urlunsplit

from semaphoreui_mcp.profiles import normalize_tool_profile


def normalize_api_url(value: str) -> str:
  """Keep reverse proxy prefixes while accepting either the UI or API URL."""
  value = value.strip()
  try:
    parsed = urlsplit(value)
    _ = parsed.port
  except ValueError:
    raise ValueError("SEMAPHORE_URL must be a valid HTTP or HTTPS URL") from None
  if (
    parsed.scheme not in {"http", "https"}
    or not parsed.hostname
    or parsed.username is not None
    or parsed.password is not None
    or parsed.query
    or parsed.fragment
    or "\\" in value
    or any(character.isspace() for character in value)
    or any(ord(character) < 32 for character in value)
  ):
    raise ValueError(
      "SEMAPHORE_URL must be an HTTP or HTTPS URL without credentials, query, or fragment"
    )
  decoded_path = parsed.path
  for _ in range(8):
    next_path = unquote(decoded_path)
    if next_path == decoded_path:
      break
    decoded_path = next_path
  if (
    "\\" in decoded_path
    or "%" in decoded_path
    or any(part in {".", ".."} for part in decoded_path.split("/"))
  ):
    raise ValueError("SEMAPHORE_URL must not contain path traversal")
  path = parsed.path.rstrip("/")
  if not path.endswith("/api"):
    path += "/api"
  return urlunsplit((parsed.scheme, parsed.netloc, path + "/", "", ""))


def _boolean(environ: dict[str, str], name: str, default: bool) -> bool:
  value = environ.get(name)
  if value is None:
    return default
  normalized = value.strip().lower()
  if normalized in {"true", "1", "yes", "on"}:
    return True
  if normalized in {"false", "0", "no", "off"}:
    return False
  raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class Settings:
  url: str
  api_token: str | None = field(default=None, repr=False)
  username: str | None = field(default=None, repr=False)
  password: str | None = field(default=None, repr=False)
  verify_tls: bool = True
  ca_bundle: str | None = None
  timeout: float = 30.0
  read_only: bool = False
  project_ids: frozenset[int] | None = None
  tool_profile: str = "full"

  def __post_init__(self) -> None:
    object.__setattr__(self, "tool_profile", normalize_tool_profile(self.tool_profile))
    object.__setattr__(self, "url", normalize_api_url(self.url))
    if self.api_token and (self.username or self.password):
      raise ValueError(
        "Configure SEMAPHORE_API_TOKEN or SEMAPHORE_USERNAME and SEMAPHORE_PASSWORD, not both"
      )
    if not self.api_token and not (self.username and self.password):
      raise ValueError("Set SEMAPHORE_API_TOKEN or both SEMAPHORE_USERNAME and SEMAPHORE_PASSWORD")
    if self.api_token and any(character.isspace() for character in self.api_token):
      raise ValueError("SEMAPHORE_API_TOKEN must not contain whitespace")
    if not math.isfinite(self.timeout) or self.timeout <= 0:
      raise ValueError("SEMAPHORE_TIMEOUT must be a finite positive number")
    if self.ca_bundle and not self.verify_tls:
      raise ValueError("SEMAPHORE_CA_BUNDLE requires SEMAPHORE_VERIFY_TLS=true")
    if self.project_ids is not None:
      if not self.project_ids or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 1
        for value in self.project_ids
      ):
        raise ValueError("SEMAPHORE_PROJECT_IDS must contain positive integer project IDs")
      object.__setattr__(self, "project_ids", frozenset(self.project_ids))

  @classmethod
  def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
    values = dict(os.environ if environ is None else environ)
    url = values.get("SEMAPHORE_URL", "").strip()
    if not url:
      raise ValueError("SEMAPHORE_URL is required")
    try:
      timeout = float(values.get("SEMAPHORE_TIMEOUT", "30"))
    except ValueError:
      raise ValueError("SEMAPHORE_TIMEOUT must be a finite positive number") from None
    project_ids = None
    if values.get("SEMAPHORE_PROJECT_IDS", "").strip():
      try:
        project_ids = frozenset(
          int(part.strip()) for part in values["SEMAPHORE_PROJECT_IDS"].split(",")
        )
      except ValueError:
        raise ValueError(
          "SEMAPHORE_PROJECT_IDS must be a comma-separated list of positive integers"
        ) from None
    return cls(
      url=url,
      api_token=values.get("SEMAPHORE_API_TOKEN", "").strip() or None,
      username=values.get("SEMAPHORE_USERNAME", "").strip() or None,
      password=values.get("SEMAPHORE_PASSWORD") or None,
      verify_tls=_boolean(values, "SEMAPHORE_VERIFY_TLS", True),
      ca_bundle=values.get("SEMAPHORE_CA_BUNDLE", "").strip() or None,
      timeout=timeout,
      read_only=_boolean(values, "SEMAPHORE_READ_ONLY", False),
      project_ids=project_ids,
      tool_profile=values.get("SEMAPHORE_TOOL_PROFILE", "full"),
    )
