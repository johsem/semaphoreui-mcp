"""Opt-in integration test using a disposable Semaphore Docker container.

Run: uv run python scripts/smoke_test.py --docker
Select another release with --image semaphoreui/semaphore:<tag>.
Only a new container is modified. Its Ansible task targets localhost inside it.
"""

import argparse
import asyncio
import json
import os
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import httpx

from semaphoreui_mcp.config import Settings
from semaphoreui_mcp.server import Application

IMAGE = "semaphoreui/semaphore:v2.19.17"
PLAYBOOK = """---
- name: MCP disposable smoke test
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Prove the MCP launched a local job
      ansible.builtin.debug:
        msg: semaphoreui-mcp-smoke-success
"""


def docker(*arguments: str, environment=None) -> str:
  result = subprocess.run(
    ["docker", *arguments], check=True, capture_output=True, text=True, env=environment
  )
  return result.stdout.strip()


async def call(app: Application, name: str, **arguments):
  result = await app.call_tool(name, arguments)
  if result.is_error:
    error = result.structured_content["error"]
    raise RuntimeError(f"{name} failed: {error['code']}: {error['message']}")
  print(f"PASS {name}", flush=True)
  return result.structured_content["data"]


async def wait_for_server(url: str) -> None:
  deadline = time.monotonic() + 90
  async with httpx.AsyncClient(timeout=2) as client:
    while time.monotonic() < deadline:
      try:
        response = await client.get(f"{url}/api/ping")
        if response.status_code == 200:
          return
      except httpx.HTTPError:
        pass
      await asyncio.sleep(0.5)
  raise RuntimeError("Disposable Semaphore server did not become ready within 90 seconds")


async def wait_for_task_output(
  app: Application, project_id: int, task_id: int, *, timeout: float = 15
) -> tuple[object, object]:
  # Semaphore persists task status separately from its periodically flushed log batches.
  deadline = time.monotonic() + timeout
  pending = ["get_task_output", "get_task_raw_output"]
  outputs = {}
  try:
    async with asyncio.timeout(timeout):
      while pending:
        for name in pending.copy():
          if time.monotonic() >= deadline:
            raise TimeoutError
          output = await call(app, name, project_id=project_id, task_id=task_id)
          if "semaphoreui-mcp-smoke-success" in json.dumps(output):
            outputs[name] = output
            pending.remove(name)
        if pending:
          await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
  except TimeoutError:
    raise RuntimeError(
      f"Task completed but expected output did not appear within {timeout:g} seconds "
      f"from {', '.join(pending)}"
    ) from None
  return outputs["get_task_output"], outputs["get_task_raw_output"]


async def exercise(url: str, password: str) -> None:
  await wait_for_server(url)
  session = Application(Settings(url=url, username="smoke-admin", password=password))
  async with session.client:
    user = await call(session, "get_current_user")
    assert user["username"] == "smoke-admin"
    token = await call(session, "create_api_token", body={"name": "Disposable MCP smoke token"})
    bearer = Application(Settings(url=url, api_token=token["id"]))
    async with bearer.client:
      assert (await call(bearer, "get_current_user"))["id"] == user["id"]
      project = await call(bearer, "create_project", body={"name": "Disposable MCP smoke"})
      project_id = project["id"]
      scoped = {"project_id": project_id}
      try:
        await call(bearer, "update_project", **scoped, body={"name": "MCP smoke verified"})
        assert (await call(bearer, "get_project", **scoped))["name"] == "MCP smoke verified"
        key = await call(
          bearer, "create_access_key", **scoped, body={"name": "No credentials", "type": "none"}
        )
        repository = await call(
          bearer,
          "create_repository",
          **scoped,
          body={
            "name": "Container-local playbooks",
            "git_url": "/tmp/mcp-smoke-repository",
            "git_branch": "",
            "ssh_key_id": key["id"],
          },
        )
        inventory = await call(
          bearer,
          "create_inventory",
          **scoped,
          body={
            "name": "Container localhost only",
            "type": "static",
            "inventory": "localhost ansible_connection=local\n",
            "ssh_key_id": key["id"],
          },
        )
        environment = await call(
          bearer,
          "create_environment",
          **scoped,
          body={"name": "Smoke variables", "json": "{}", "env": "{}"},
        )
        template = await call(
          bearer,
          "create_template",
          **scoped,
          body={
            "name": "Local debug task",
            "app": "ansible",
            "playbook": "smoke.yml",
            "inventory_id": inventory["id"],
            "repository_id": repository["id"],
            "environment_id": environment["id"],
            "arguments": "[]",
          },
        )
        schedule = await call(
          bearer,
          "create_schedule",
          **scoped,
          body={
            "name": "Disabled smoke schedule",
            "template_id": template["id"],
            "cron_format": "0 0 1 1 *",
            "active": False,
          },
        )
        await call(bearer, "get_schedule", **scoped, schedule_id=schedule["id"])
        core = Application(
          Settings(
            url=url,
            api_token=token["id"],
            tool_profile="core",
            project_ids=frozenset({project_id}),
          )
        )
        async with core.client:
          await call(core, "list_templates", **scoped)
          task = await call(core, "create_task", **scoped, body={"template_id": template["id"]})
          completed = await call(
            core,
            "wait_for_task",
            **scoped,
            task_id=task["id"],
            timeout=90,
            poll_interval=0.5,
            include_output=True,
          )
          if completed["task"]["status"] != "success":
            # This container contains only the fixtures above, never user credentials.
            print(completed.get("output", []), flush=True)
            if not completed["finished"]:
              await call(core, "stop_task", **scoped, task_id=task["id"], body={"force": True})
              await call(core, "wait_for_task", **scoped, task_id=task["id"], timeout=30)
            raise RuntimeError("The container-local Ansible task did not finish successfully")
          output, raw_output = await wait_for_task_output(core, **scoped, task_id=task["id"])
          assert "semaphoreui-mcp-smoke-success" in json.dumps(output)
          assert "semaphoreui-mcp-smoke-success" in str(raw_output)
          print("PASS core profile task workflow", flush=True)
        await call(bearer, "get_project_backup", **scoped)
        await call(bearer, "delete_schedule", **scoped, schedule_id=schedule["id"])
        await call(bearer, "delete_task", **scoped, task_id=task["id"])
        await call(bearer, "delete_template", **scoped, template_id=template["id"])
        await call(bearer, "delete_environment", **scoped, environment_id=environment["id"])
        await call(bearer, "delete_inventory", **scoped, inventory_id=inventory["id"])
        await call(bearer, "delete_repository", **scoped, repository_id=repository["id"])
        await call(bearer, "delete_access_key", **scoped, key_id=key["id"])
      finally:
        await call(bearer, "delete_project", **scoped)
      assert not await call(bearer, "list_projects")
    await call(session, "delete_api_token", token_id=token["id"])


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "--docker",
    action="store_true",
    help="Explicitly start, exercise, and remove a new disposable Semaphore container",
  )
  parser.add_argument(
    "--image",
    default=IMAGE,
    help=f"Semaphore image to exercise (default: {IMAGE})",
  )
  args = parser.parse_args()
  if not args.docker:
    parser.error("Pass --docker to opt in to creating the disposable test container")
  name = f"semaphoreui-mcp-smoke-{uuid.uuid4().hex[:12]}"
  password = secrets.token_urlsafe(24)
  container = None
  try:
    environment = {**os.environ, "SEMAPHORE_ADMIN_PASSWORD": password}
    container = docker(
      "run",
      "--detach",
      "--rm",
      "--name",
      name,
      "--publish",
      "127.0.0.1::3000",
      "--env",
      "SEMAPHORE_DB_DIALECT=sqlite",
      "--env",
      "SEMAPHORE_ADMIN=smoke-admin",
      "--env",
      "SEMAPHORE_ADMIN_PASSWORD",
      "--env",
      "SEMAPHORE_ADMIN_NAME=Smoke",
      "--env",
      "SEMAPHORE_ADMIN_EMAIL=smoke@localhost",
      args.image,
      environment=environment,
    )
    address = docker("port", container, "3000/tcp")
    if not address.startswith("127.0.0.1:") or "\n" in address:
      raise RuntimeError("Expected exactly one loopback test port")
    with tempfile.TemporaryDirectory(prefix="semaphoreui-mcp-smoke-") as directory:
      repository = Path(directory) / "repository"
      repository.mkdir(mode=0o755)
      (repository / "smoke.yml").write_text(PLAYBOOK)
      docker("cp", str(repository), f"{container}:/tmp/mcp-smoke-repository")
    asyncio.run(exercise(f"http://{address}", password))
    print(f"Live Semaphore smoke test passed: {args.image}", flush=True)
  finally:
    if container:
      docker("rm", "--force", "--volumes", container)
      print("Removed disposable test container.", flush=True)


if __name__ == "__main__":
  main()
