import json
import sys

import pytest

from semaphoreui_mcp import __main__ as cli
from semaphoreui_mcp.catalogue import load_catalogue
from semaphoreui_mcp.profiles import CORE_TOOLS


@pytest.mark.parametrize(
  ("environment_profile", "arguments", "core"),
  [
    (None, [], False),
    ("core", [], True),
    ("full", ["--tool-profile", "core"], True),
    ("core", ["--tool-profile", "full"], False),
  ],
)
def test_offline_catalogue_selects_profile_without_credentials(
  monkeypatch, capsys, environment_profile, arguments, core
):
  for name in (
    "SEMAPHORE_URL",
    "SEMAPHORE_API_TOKEN",
    "SEMAPHORE_USERNAME",
    "SEMAPHORE_PASSWORD",
    "SEMAPHORE_TOOL_PROFILE",
  ):
    monkeypatch.delenv(name, raising=False)
  if environment_profile:
    monkeypatch.setenv("SEMAPHORE_TOOL_PROFILE", environment_profile)

  def unexpected(*args, **kwargs):
    raise AssertionError("Offline discovery must not initialize a configured HTTP client")

  monkeypatch.setattr(cli, "Application", unexpected)
  monkeypatch.setattr(cli.Settings, "from_env", unexpected)
  monkeypatch.setattr(sys, "argv", ["semaphoreui-mcp", "--list-tools", *arguments])
  cli.main()
  names = {tool["name"] for tool in json.loads(capsys.readouterr().out)}
  assert names == (CORE_TOOLS if core else load_catalogue().keys() | {"wait_for_task"})


@pytest.mark.parametrize("profile", ["", "unknown"])
def test_offline_catalogue_rejects_invalid_profile(monkeypatch, capsys, profile):
  monkeypatch.setenv("SEMAPHORE_TOOL_PROFILE", profile)
  monkeypatch.setattr(sys, "argv", ["semaphoreui-mcp", "--list-tools"])
  with pytest.raises(SystemExit) as error:
    cli.main()
  assert error.value.code == 2
  assert "SEMAPHORE_TOOL_PROFILE must be full or core" in capsys.readouterr().err


def test_runtime_cli_profile_overrides_environment(monkeypatch):
  monkeypatch.setenv("SEMAPHORE_URL", "https://semaphore.test")
  monkeypatch.setenv("SEMAPHORE_API_TOKEN", "test-token")
  monkeypatch.setenv("SEMAPHORE_TOOL_PROFILE", "core")
  monkeypatch.delenv("SEMAPHORE_USERNAME", raising=False)
  monkeypatch.delenv("SEMAPHORE_PASSWORD", raising=False)
  monkeypatch.setattr(sys, "argv", ["semaphoreui-mcp", "--tool-profile", "full"])
  seen = []

  async def run(application):
    async with application.client:
      seen.append(application.settings.tool_profile)

  monkeypatch.setattr(cli, "run_stdio", run)
  cli.main()
  assert seen == ["full"]
