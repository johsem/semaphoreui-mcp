import pytest

from semaphoreui_mcp.config import Settings


def environment(**overrides):
  return {
    "SEMAPHORE_URL": "https://semaphore.example",
    "SEMAPHORE_API_TOKEN": "configured-api-token",
    **overrides,
  }


@pytest.mark.parametrize(
  ("url", "expected"),
  [
    ("https://semaphore.example", "https://semaphore.example/api/"),
    ("https://semaphore.example/", "https://semaphore.example/api/"),
    ("https://semaphore.example/api", "https://semaphore.example/api/"),
    ("https://semaphore.example/api/", "https://semaphore.example/api/"),
    ("http://localhost:3000/semaphore", "http://localhost:3000/semaphore/api/"),
    ("https://semaphore.example/proxy/api/", "https://semaphore.example/proxy/api/"),
    ("http://[::1]:3000", "http://[::1]:3000/api/"),
  ],
)
def test_api_url_preserves_reverse_proxy_prefix(url, expected):
  settings = Settings.from_env(environment(SEMAPHORE_URL=url))
  assert settings.url == expected


def test_safe_defaults():
  settings = Settings.from_env(environment())
  assert settings.verify_tls is True
  assert settings.timeout == 30
  assert settings.read_only is False
  assert settings.project_ids is None
  assert "configured-api-token" not in repr(settings)


def test_session_credentials_and_options():
  settings = Settings.from_env(
    {
      "SEMAPHORE_URL": "https://semaphore.example",
      "SEMAPHORE_USERNAME": "admin",
      "SEMAPHORE_PASSWORD": " password with spaces ",
      "SEMAPHORE_TIMEOUT": "12.5",
      "SEMAPHORE_READ_ONLY": "yes",
      "SEMAPHORE_PROJECT_IDS": "1, 2,2,31",
      "SEMAPHORE_CA_BUNDLE": "/tmp/private-ca.pem",
    }
  )
  assert settings.username == "admin"
  assert settings.password == " password with spaces "
  assert "password with spaces" not in repr(settings)
  assert settings.timeout == 12.5
  assert settings.read_only is True
  assert settings.project_ids == frozenset({1, 2, 31})
  assert settings.ca_bundle == "/tmp/private-ca.pem"


@pytest.mark.parametrize(
  "url",
  [
    "",
    "semaphore.example",
    "ftp://semaphore.example",
    "https://user:password@semaphore.example",
    "https://semaphore.example?token=secret",
    "https://semaphore.example/#fragment",
    "https://semaphore.example:invalid/",
    "https://semaphore.example/../admin",
    "https://semaphore.example/%2e%2e/admin",
    "https://semaphore.example/%252e%252e/admin",
    "https://semaphore.example\\evil/",
    "https://semaphore.example/a b",
    "https://[broken",
  ],
)
def test_invalid_urls_fail_without_echoing_input(url):
  with pytest.raises(ValueError, match="SEMAPHORE_URL") as error:
    Settings.from_env(environment(SEMAPHORE_URL=url))
  assert "token=secret" not in str(error.value)
  assert "user:password" not in str(error.value)


@pytest.mark.parametrize(
  "options",
  [
    {"SEMAPHORE_API_TOKEN": ""},
    {"SEMAPHORE_API_TOKEN": "", "SEMAPHORE_USERNAME": "admin"},
    {"SEMAPHORE_API_TOKEN": "", "SEMAPHORE_PASSWORD": "private-password"},
    {"SEMAPHORE_USERNAME": "admin", "SEMAPHORE_PASSWORD": "private-password"},
    {"SEMAPHORE_API_TOKEN": "private-token\r\nAuthorization: evil"},
  ],
)
def test_invalid_authentication_fails_without_echoing_credentials(options):
  with pytest.raises(ValueError) as error:
    Settings.from_env(environment(**options))
  assert "private-password" not in str(error.value)
  assert "private-token" not in str(error.value)


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "broken"])
def test_invalid_timeouts(timeout):
  with pytest.raises(ValueError, match="SEMAPHORE_TIMEOUT"):
    Settings.from_env(environment(SEMAPHORE_TIMEOUT=timeout))


@pytest.mark.parametrize("project_ids", ["0", "-1", "1,no", "1,,2", "1,"])
def test_invalid_project_allowlists(project_ids):
  with pytest.raises(ValueError, match="SEMAPHORE_PROJECT_IDS"):
    Settings.from_env(environment(SEMAPHORE_PROJECT_IDS=project_ids))


def test_invalid_boolean_is_rejected():
  with pytest.raises(ValueError, match="SEMAPHORE_READ_ONLY"):
    Settings.from_env(environment(SEMAPHORE_READ_ONLY="sometimes"))


def test_custom_ca_cannot_silently_disable_tls_verification():
  with pytest.raises(ValueError, match="SEMAPHORE_CA_BUNDLE"):
    Settings.from_env(environment(SEMAPHORE_VERIFY_TLS="false", SEMAPHORE_CA_BUNDLE="/tmp/ca.pem"))


def test_environment_is_read_at_call_time(monkeypatch):
  monkeypatch.setenv("SEMAPHORE_URL", "http://localhost:3000")
  monkeypatch.setenv("SEMAPHORE_API_TOKEN", "test-api-token")
  monkeypatch.delenv("SEMAPHORE_USERNAME", raising=False)
  monkeypatch.delenv("SEMAPHORE_PASSWORD", raising=False)
  assert Settings.from_env().api_token == "test-api-token"
