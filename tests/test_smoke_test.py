import asyncio
import importlib.util
from collections import Counter, deque
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/smoke_test.py"
SPEC = importlib.util.spec_from_file_location("smoke_test", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)

MARKER = "semaphoreui-mcp-smoke-success"


class OutputApplication:
  def __init__(self, structured, raw):
    self.responses = {"get_task_output": deque(structured), "get_task_raw_output": deque(raw)}
    self.calls = []

  async def call_tool(self, name, arguments):
    self.calls.append((name, arguments))
    responses = self.responses[name]
    output = responses.popleft() if len(responses) > 1 else responses[0]
    return SimpleNamespace(is_error=False, structured_content={"data": output})


@pytest.fixture
def clock(monkeypatch):
  clock = SimpleNamespace(now=0.0, delays=[])

  async def sleep(delay):
    clock.delays.append(delay)
    clock.now += delay

  monkeypatch.setattr(smoke, "time", SimpleNamespace(monotonic=lambda: clock.now))
  monkeypatch.setattr(smoke, "asyncio", SimpleNamespace(timeout=asyncio.timeout, sleep=sleep))
  return clock


async def test_output_wait_retries_each_endpoint_until_its_logs_are_persisted(clock):
  structured = [{"output": MARKER}]
  app = OutputApplication([[], structured], ["", "Starting", MARKER])
  output, raw = await smoke.wait_for_task_output(app, project_id=7, task_id=4)
  assert output == structured
  assert raw == MARKER
  assert clock.now == 0.5
  assert [name for name, _ in app.calls] == [
    "get_task_output",
    "get_task_raw_output",
    "get_task_output",
    "get_task_raw_output",
    "get_task_raw_output",
  ]
  assert all(arguments == {"project_id": 7, "task_id": 4} for _, arguments in app.calls)


@pytest.mark.parametrize("missing", ["get_task_output", "get_task_raw_output"])
async def test_output_wait_fails_within_deadline_if_either_marker_never_appears(clock, missing):
  app = OutputApplication(
    [[]] if missing == "get_task_output" else [[{"output": MARKER}]],
    [""] if missing == "get_task_raw_output" else [MARKER],
  )
  with pytest.raises(RuntimeError, match=f"within 0.6 seconds from {missing}"):
    await smoke.wait_for_task_output(app, project_id=7, task_id=4, timeout=0.6)
  assert clock.now == 0.6
  assert clock.delays == pytest.approx([0.25, 0.25, 0.1])
  counts = Counter(name for name, _ in app.calls)
  assert counts[missing] == 3
  assert sum(counts.values()) == 4


async def test_output_wait_bounds_a_stalled_upstream_request():
  cancelled = False

  async def pending(*args, **kwargs):
    nonlocal cancelled
    try:
      await asyncio.Event().wait()
    finally:
      cancelled = True

  app = SimpleNamespace(call_tool=pending)
  with pytest.raises(RuntimeError, match="within 0.01 seconds"):
    await asyncio.wait_for(
      smoke.wait_for_task_output(app, project_id=7, task_id=4, timeout=0.01), timeout=1
    )
  assert cancelled


async def test_output_wait_does_not_retry_or_hide_api_errors(clock):
  calls = []

  async def denied(name, arguments):
    calls.append(name)
    return SimpleNamespace(
      is_error=True,
      structured_content={"error": {"code": "forbidden", "message": "Denied"}},
    )

  with pytest.raises(RuntimeError, match="get_task_output failed: forbidden: Denied"):
    await smoke.wait_for_task_output(SimpleNamespace(call_tool=denied), project_id=7, task_id=4)
  assert calls == ["get_task_output"]
  assert not clock.delays
