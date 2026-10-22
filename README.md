# Semaphore UI MCP server

A Python [Model Context Protocol](https://modelcontextprotocol.io/) server for
[Semaphore UI](https://semaphoreui.com/). Connect an MCP client to inspect automation,
manage project configuration, launch jobs, and troubleshoot task output through
Semaphore's management API.

It provides named, schema-validated management API tools and a `wait_for_task`
helper, including routes omitted from the upstream OpenAPI document. The server
works over stdio or Streamable HTTP and uses the official Python MCP SDK.

## Capabilities

- Projects and project membership, global users, API tokens, and server information.
- Templates, task execution, task status and logs, task cancellation, and a bounded
  `wait_for_task` helper.
- Inventories, repositories, environments, variable groups, access keys, schedules,
  views, and integrations.
- Management routes for runners, credentials, and edition-specific features where
  the Semaphore instance and account permit them.
- Read-only MCP resources for discovering projects and inspecting their configuration.
- Diagnostic prompts for investigating tasks and preparing template runs.
- API-token or username/password authentication, custom CA certificates, bounded
  request timeouts, read-only mode, and a project allowlist.

See the complete [API coverage reference](docs/api-coverage.md) for tool names,
HTTP routes, API-source provenance, and exclusions. Edition-specific tools are
advertised consistently; the Semaphore server determines whether an operation is
available to the configured account.

## Install and run

Requires Python 3.13+. [uv](https://docs.astral.sh/uv/) is the recommended installer;
a pip installation is also supported below.

```sh
git clone https://github.com/johsem/semaphoreui-mcp.git
cd semaphoreui-mcp
uv sync --locked
export SEMAPHORE_URL="https://semaphore.example.com"
export SEMAPHORE_API_TOKEN="your-api-token"
uv run --frozen semaphoreui-mcp
```

The default transport is stdio. An MCP client starts the process and exchanges
protocol messages through its standard input and output. Operational logs go to
standard error. Running the command directly will wait for an MCP client.

Check the installed version or inspect the catalogue without contacting Semaphore:

```sh
uv run --frozen semaphoreui-mcp --version
uv run --frozen semaphoreui-mcp --list-tools
```

To install without uv, create a Python 3.13+ virtual environment and run
`python -m pip install .` inside it. This resolves dependencies from the ranges in
`pyproject.toml`; `uv sync --locked` uses the repository's exact dependency lock.

For versioned wheels, PyPI packages, and prebuilt containers, see
[installing a release](docs/installing.md). Use the channels listed in the chosen
[GitHub release](https://github.com/johsem/semaphoreui-mcp/releases).

## Connect an MCP client

Use this configuration in a client that supports the common `mcpServers` format,
replacing the absolute checkout path and credentials:

```json
{
  "mcpServers": {
    "semaphore": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/semaphoreui-mcp",
        "run",
        "--frozen",
        "semaphoreui-mcp"
      ],
      "env": {
        "SEMAPHORE_URL": "https://semaphore.example.com",
        "SEMAPHORE_API_TOKEN": "your-api-token",
        "SEMAPHORE_TOOL_PROFILE": "core",
        "SEMAPHORE_READ_ONLY": "true",
        "SEMAPHORE_PROJECT_IDS": "1,2"
      }
    }
  }
}
```

This example selects the core tool profile with read-only access to projects 1
and 2. Remove the project allowlist to use the whole account's scope;
set `SEMAPHORE_READ_ONLY=false` to enable task launches. Use the full profile for
configuration changes. The MCP server cannot grant permissions beyond
those of its Semaphore account.

If uv is unavailable on the MCP client's executable search path, use its absolute
path, or set `command` to the installed virtual environment's absolute
`bin/semaphoreui-mcp` path and omit `args`.

## Configuration

Configuration is read from environment variables. The process does not implicitly
load `.env`; pass variables through your client, shell, or container configuration.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SEMAPHORE_URL` | Required | Server root URL or URL ending in `/api`; reverse-proxy path prefixes are supported. |
| `SEMAPHORE_API_TOKEN` | Unset | Semaphore API token. Prefer a dedicated account with the permissions needed for your workflow. |
| `SEMAPHORE_USERNAME` | Unset | Username for session login when no API token is configured. |
| `SEMAPHORE_PASSWORD` | Unset | Password paired with `SEMAPHORE_USERNAME`. |
| `SEMAPHORE_VERIFY_TLS` | `true` | Validate Semaphore's HTTPS certificate. Disable only for a deliberately trusted development environment. |
| `SEMAPHORE_CA_BUNDLE` | Unset | Path to a PEM CA bundle for a private certificate authority. |
| `SEMAPHORE_TIMEOUT` | `30` | Upstream HTTP request timeout in seconds. |
| `SEMAPHORE_TOOL_PROFILE` | `full` | `core` exposes everyday inspection and task tools; `full` exposes the management catalogue. |
| `SEMAPHORE_READ_ONLY` | `false` | Disable management mutations and job execution. |
| `SEMAPHORE_PROJECT_IDS` | Unset | Comma-separated positive project IDs. Restrict project access and block global administration. |
| `MCP_HTTP_TOKEN` | Unset | Bearer token protecting Streamable HTTP. Required for non-loopback bindings, optional on loopback. |
| `MCP_ALLOWED_HOSTS` | Local host patterns | Comma-separated allowed HTTP host patterns. Include the hostname used by external clients. |
| `MCP_ALLOWED_ORIGINS` | Local HTTP origin patterns | Optional comma-separated origin allowlist for the MCP SDK's DNS rebinding protection. |

Configure either an API token or a complete username/password pair. For accounts
requiring interactive SSO or two-factor login, use an API token. `.env.example`
contains a complete environment template; `.env` is ignored by Git and excluded
from the Docker build context.

The project allowlist also filters project discovery. Global operations that
cannot be scoped to a project are blocked, apart from safe server information and
filtered project listing. Semaphore remains responsible for enforcing account
permissions on each upstream request.

Keep configuration files containing tokens private. Tool responses and task logs
can contain sensitive values supplied by Semaphore, including variables or output
from automation. Review what your MCP client stores and shares. Read-only mode
prevents mutations; it does not sanitize all upstream data.

## Choose a tool profile

Use `SEMAPHORE_TOOL_PROFILE=core` for inspecting projects and template dependencies,
running or stopping tasks, and reading their status and output. It keeps the tool
list focused on everyday operations. Use `full` when you need configuration
changes, user administration, or edition-specific management operations. The
default remains `full` for existing configurations.

The CLI option `--tool-profile core` or `--tool-profile full` overrides the
environment variable. Inspect either profile without credentials or a connection:

```sh
uv run --frozen semaphoreui-mcp --list-tools --tool-profile core
uv run --frozen semaphoreui-mcp --list-tools --tool-profile full
```

Offline listing shows the selected profile's catalogue. At runtime, read-only mode
and the project allowlist further restrict available tools. Tools excluded by the
profile cannot be called by name either. The core profile still allows task
execution; combine it with `SEMAPHORE_READ_ONLY=true` for inspection-only access.
Resources and prompts remain available under both profiles and retain the same
access restrictions. Restart the server after changing its profile.

## Common workflows

Tool inputs use named path/query parameters and a `body` object for JSON requests.
Inspect the tool's advertised schema before using optional fields; the catalogue
keeps the upstream field names and validates inputs locally.

For standard project-resource create/update operations, the adapter fills body
`project_id` and resource `id` from the path parameters where required by the API.
Supplying a conflicting ID is rejected before making the request.

1. Call `list_projects` to discover project IDs.
2. Call `list_templates` with `{"project_id": 1}` to discover templates.
3. Inspect the selected template and its inventory, environment, and repository.
4. Launch a task with `create_task`:

   ```json
   {
     "project_id": 1,
     "body": {
       "template_id": 2
     }
   }
   ```

5. Use the returned task ID with `get_task`, `get_task_output`, or
   `get_task_raw_output`, each taking `project_id` and `task_id`.
6. Use `wait_for_task` to poll within a bounded time instead of repeatedly making
   manual status calls. A timeout ends polling; it does not cancel the job.

For example, call `wait_for_task` with:

```json
{
  "project_id": 1,
  "task_id": 123,
  "timeout": 60,
  "poll_interval": 2,
  "include_output": true,
  "tail_lines": 100
}
```

Its `timeout` stops further polling. The initial status request and optional
output fetch follow `SEMAPHORE_TIMEOUT` and the HTTP client's retry rules
separately, so total elapsed time can exceed the polling timeout. The result
includes the last task state, `finished`, and `timed_out`.

The optional output is a snapshot. Semaphore can persist final log lines after
the task reports completion; fetch task output again if those lines are not yet
available.

For task history, `list_recent_tasks` and `list_recent_template_tasks` accept
`count` and a `before` task ID cursor. A template listing supports its advertised
sort/order/app filters; task output endpoints do not support pagination.

Task creation runs real automation with the template's privileges. For an Ansible
template that supports check mode, the task body can include
`"params": {"dry_run": true}`. The task API's `environment` and `arguments`
fields are JSON-encoded **strings**, when supplied, rather than nested JSON values.

To cancel a task:

```json
{
  "project_id": 1,
  "task_id": 123,
  "body": {
    "force": false
  }
}
```

Send that input to `stop_task`. Use the task's latest status and output to verify
what stopped and whether any changes had already been made.

## Resources and prompts

MCP clients that support resources can read:

| Resource URI | Content |
| --- | --- |
| `semaphore://capabilities` | Server capabilities and API compatibility information. |
| `semaphore://projects` | Visible projects, respecting the allowlist. |
| `semaphore://projects/{project_id}/{collection}` | Project data; collection is `project`, `templates`, `tasks`, `inventory`, `repositories`, `environments`, or `schedules`. |
| `semaphore://projects/{project_id}/tasks/{task_id}` | An individual task. |

The `investigate_task` prompt guides diagnosis using task metadata and output. The
`plan_template_run` prompt guides inspection of the template and its dependencies
before execution. Prompts provide a workflow; they do not launch jobs themselves.

## Streamable HTTP

Start locally:

```sh
export MCP_HTTP_TOKEN="a-separate-long-random-token"
uv run --frozen semaphoreui-mcp \
  --transport streamable-http --host 127.0.0.1 --port 8000
```

Connect your client's Streamable HTTP transport to `http://127.0.0.1:8000/mcp`,
with an `Authorization: Bearer <MCP_HTTP_TOKEN>` request header when the token is
configured. All MCP HTTP requests must carry the configured token. This service
uses one Semaphore credential identity for every connected client and stateless
MCP HTTP sessions. It does not implement per-user OAuth or a multi-tenant login.

For a LAN or reverse-proxy deployment, set `MCP_HTTP_TOKEN` and add the public host
to `MCP_ALLOWED_HOSTS`, for example `mcp.example.com`. Configure
`MCP_ALLOWED_ORIGINS` if your client sends an Origin header. Terminate HTTPS at your
reverse proxy before sending credentials across an untrusted network. Binding to
`0.0.0.0` or `::` requires a token even when the container port is published only
on the host's loopback interface.

## Docker

```sh
cp .env.example .env
# Edit .env: set the Semaphore URL/token and a separate MCP_HTTP_TOKEN.
docker compose up --build -d
```

The container runs as an unprivileged user and Compose publishes port 8000 only on
`127.0.0.1`. Connect to `http://127.0.0.1:8000/mcp` with the bearer token. The image
installs runtime dependencies from `uv.lock`; Compose uses a read-only root
filesystem and a writable temporary directory. For a custom CA bundle, mount the
PEM file read-only and set `SEMAPHORE_CA_BUNDLE` to its path inside the container.

To use the image over stdio instead:

```sh
docker build -t semaphoreui-mcp .
docker run --rm -i --env-file .env semaphoreui-mcp --transport stdio
```

Do not allocate a TTY (`-t`) for stdio MCP. The image's default command starts HTTP;
the explicit `--transport stdio` argument overrides it.

## systemd service

To run the HTTP transport as a supervised service on a Linux host or container
running systemd, install the package into a uv-managed virtual environment and use
[`deploy/semaphoreui-mcp.service`](deploy/semaphoreui-mcp.service) as a template.
Run these commands from a source checkout or extracted source distribution, with
Git and uv installed. The example expects a system-wide uv executable at
`/usr/local/bin/uv`; adjust that path if needed. A uv installation in your personal
home directory may not be accessible to the service user.

```sh
sudo useradd --system --user-group --home /opt/semaphoreui-mcp --shell /usr/sbin/nologin semaphoreui-mcp
sudo mkdir -p /opt/semaphoreui-mcp && sudo chown semaphoreui-mcp: /opt/semaphoreui-mcp
sudo -u semaphoreui-mcp env UV_PYTHON_INSTALL_DIR=/opt/semaphoreui-mcp/uv sh -c '
  /usr/local/bin/uv venv /opt/semaphoreui-mcp/venv --python 3.13 &&
  /usr/local/bin/uv pip install --python /opt/semaphoreui-mcp/venv/bin/python \
    "semaphoreui-mcp @ git+https://github.com/johsem/semaphoreui-mcp"'
sudo install -o root -g semaphoreui-mcp -m 0640 .env.example /etc/semaphoreui-mcp.env
sudoedit /etc/semaphoreui-mcp.env
```

Replace the placeholder Semaphore URL and credentials and set `MCP_HTTP_TOKEN`
before starting the service. The unit loads this file via `EnvironmentFile` and
runs with `NoNewPrivileges`/`ProtectSystem=strict`. Pin the package source to a
commit (`...semaphoreui-mcp@<sha>`) when deploying a specific revision; dependency
versions are still resolved from the package's allowed ranges.

The template listens on `127.0.0.1:8000`. Adjust `--host`, `--port`,
`MCP_ALLOWED_HOSTS`, and the paths for your environment before installing it:

```sh
sudo install -o root -g root -m 0644 deploy/semaphoreui-mcp.service /etc/systemd/system/semaphoreui-mcp.service
sudo systemctl daemon-reload
sudo systemctl enable --now semaphoreui-mcp
sudo systemctl status semaphoreui-mcp
```

Connect to `http://127.0.0.1:8000/mcp` with the configured bearer token. Follow the
[HTTP configuration](#streamable-http) guidance when exposing it through a TLS
reverse proxy. View service logs with `sudo journalctl -u semaphoreui-mcp`.

## Development and validation

```sh
uv sync --locked --group dev
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=semaphoreui_mcp --cov-report=term-missing
uv run --frozen python -m build
```

Unit and protocol tests use controlled HTTP responses and local MCP sessions.
They do not need live Semaphore credentials or execute real automation.
[GitHub Actions](.github/workflows/ci.yml) runs lint, tests, catalogue discovery,
package builds, and disposable-container compatibility tests on pushes, pull
requests, and manual runs. Test reports and built distributions are saved as
workflow artifacts. GitLab CI remains available for GitLab-hosted repositories.
Python tests run on 3.13, 3.14, and 3.15. Weekly Dependabot pull requests cover
Python dependencies, GitHub Actions, and Docker base images.

An optional integration smoke test verifies the adapter against a disposable
Semaphore Community container:

```sh
uv run --frozen python scripts/smoke_test.py --docker
```

Use `--image semaphoreui/semaphore:<tag>` to test another release. The default
image and recorded results are listed in [API coverage](docs/api-coverage.md).

It requires Docker and downloads the Semaphore image if needed. The script creates
a unique container with temporary credentials and a random loopback port. It
exercises cookie login and API-token creation/use/revocation, project CRUD,
access-key/repository/inventory/environment/template/schedule creation and cleanup,
template listing, schedule reads, task execution and output, and project backup.
Its Ansible task runs a debug-only playbook inside that container. The
script removes its container and anonymous volumes afterwards; the downloaded
image remains cached. It does not use your configured Semaphore instance.

The tested releases and scope are recorded in [API coverage](docs/api-coverage.md).
Deployment-specific permissions, SSO policy, external runner connectivity, and
Pro-only routes still need validation against the intended deployment.

The catalogue is bundled with the package so discovery does not require network
access or a running Semaphore server. When adding or updating API coverage, review
upstream API and router changes, update the bundled specification and
`src/semaphoreui_mcp/data/overrides.json` as needed, update the coverage reference,
and run the test suite and relevant smoke tests. Tool schemas are built from these
files at startup; keep existing tool names stable.

## Compatibility and scope

The server does not require a particular Semaphore release or reject instances
based on their version. Existing tools are expected to work with newer releases
that preserve the API routes, request formats, and behavior they use. They can also
work with older releases where those APIs are available. New upstream features
may require a catalogue update before they are exposed as tools.

Compatibility is per operation: older versions may lack routes or fields, and
breaking API changes may require adapter updates. The catalogue does not
automatically detect or hide operations missing from a particular installation.
See [API coverage](docs/api-coverage.md) for tested versions, validation scope,
and the source release used to build the bundled schemas. That source records API
provenance, not a required server version.

The bundled OpenAPI source and applicable upstream license are included in package
data. This is an independent integration with
[the Semaphore project](https://github.com/semaphoreui/semaphore).

The MCP exposes management operations. Interactive login/SSO flows, WebSocket
subscriptions, runner agent transport, incoming integration webhooks, the
Terraform backend protocol, and JWKS endpoints are outside that interface.
Username/password session setup is handled internally by the HTTP client.
Unsupported routes and account/edition limitations return errors from Semaphore;
consult [API coverage](docs/api-coverage.md) for the precise boundary.

## Help and contributions

Bug reports and contributions are welcome through
[GitHub issues](https://github.com/johsem/semaphoreui-mcp/issues) and pull requests.
For a compatibility or connection problem, include the MCP server version,
Semaphore version and edition, MCP client, transport, affected tool, and a minimal
reproduction with sanitized error output. Remove tokens, passwords, private
configuration, and sensitive task output before sharing.

For code changes, use the development checks above and add regression coverage
for changed behavior. API changes should include updated tool schemas, coverage
documentation, and a smoke-test result for the affected Semaphore release when
possible.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and
[catalogue maintenance](docs/catalogue-maintenance.md) for API updates. Report
vulnerabilities privately using [SECURITY.md](SECURITY.md). Maintainers can follow
the [release guide](docs/releasing.md); user-facing changes are recorded in the
[changelog](CHANGELOG.md).

## License

This project is licensed under the [MIT License](LICENSE).
The bundled Semaphore API specification retains its upstream copyright notices
and [MIT license](src/semaphoreui_mcp/data/SEMAPHORE-LICENSE).
