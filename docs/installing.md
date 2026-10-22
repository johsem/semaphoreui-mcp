# Installing a release

Choose a version from [GitHub Releases](https://github.com/johsem/semaphoreui-mcp/releases)
and use the distribution channels listed in its release notes. The commands below
apply after that version is published to the corresponding channel. Before the
first release, or when developing the adapter, use the
[source checkout instructions](../README.md#install-and-run).

## Python package

For a version published to PyPI, install it in an isolated environment:

```sh
uv tool install "semaphoreui-mcp==<version>"
semaphoreui-mcp --version
semaphoreui-mcp --list-tools --tool-profile core
```

Replace `<version>` with the selected package version, without the Git tag's `v`
prefix. A Python 3.13+ virtual environment with
`python -m pip install semaphoreui-mcp==<version>` is also supported.

Alternatively, download the wheel and `SHA256SUMS` from the GitHub release.
Verify the wheel's checksum against the published file and install that local
wheel with `uv tool install /absolute/path/to/semaphoreui_mcp-<version>-py3-none-any.whl`.
This path does not require the package to be published to PyPI.

Configure the installed executable in your MCP client:

```json
{
  "mcpServers": {
    "semaphore": {
      "command": "/absolute/path/to/semaphoreui-mcp",
      "env": {
        "SEMAPHORE_URL": "https://semaphore.example.com",
        "SEMAPHORE_API_TOKEN": "your-api-token",
        "SEMAPHORE_TOOL_PROFILE": "core",
        "SEMAPHORE_READ_ONLY": "true"
      }
    }
  }
}
```

Find the installed path with `command -v semaphoreui-mcp`. Add
`SEMAPHORE_PROJECT_IDS` to restrict projects. Enable writes only when needed;
task execution uses the configured Semaphore account's permissions.

## Prebuilt container

For a release with a published GHCR image, use its exact version tag:

```sh
docker pull "ghcr.io/johsem/semaphoreui-mcp:<version>"
docker run --rm -i --env-file .env \
  "ghcr.io/johsem/semaphoreui-mcp:<version>" --transport stdio
```

Create `.env` using the [environment template](../.env.example), or supply the
variables through your container manager. Do not allocate a TTY for stdio MCP.
Images target Linux amd64 and arm64. Use the release's image digest for a deployment
that must retain the exact same image bytes.

For Streamable HTTP, set a separate `MCP_HTTP_TOKEN` and publish the container only
on loopback unless a trusted TLS reverse proxy handles external access:

```sh
docker run --rm --env-file .env \
  --publish 127.0.0.1:8000:8000 \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
  "ghcr.io/johsem/semaphoreui-mcp:<version>"
```

Connect to `http://127.0.0.1:8000/mcp` with the configured bearer token. See the
[HTTP configuration](../README.md#streamable-http) for host/origin allowlists and
reverse-proxy requirements.

## Upgrades

Read the release notes and [changelog](../CHANGELOG.md), test the update against a
disposable or staging Semaphore installation, then change the pinned package or
image version and restart the MCP server. Keep the previous version available for
rollback. The adapter version and the connected Semaphore version are independent;
see the [compatibility reference](api-coverage.md).
