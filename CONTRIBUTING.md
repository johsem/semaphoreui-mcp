# Contributing

Bug reports, documentation fixes, compatibility reports, and pull requests are
welcome. For a substantial feature, open an issue describing the workflow it
should enable before investing in an implementation.

Report vulnerabilities privately using the process in [SECURITY.md](SECURITY.md).
Public issues, pull requests, and logs must not contain tokens, passwords, private
keys, sensitive variables, or private task output.

## Development setup

Use Python 3.13+ and [uv](https://docs.astral.sh/uv/). Fork the repository on GitHub,
clone your fork, and create a branch for the change:

```sh
git clone https://github.com/YOUR-USERNAME/semaphoreui-mcp.git
cd semaphoreui-mcp
git switch -c fix/describe-the-change
uv sync --locked --group dev
```

The unit and MCP transport tests use mocked upstream requests and local sessions.
They do not need a Semaphore account or production credentials. The project uses
two-space Python indentation, double-quoted strings, and Ruff for formatting and
linting; configuration lives in `pyproject.toml`.

## Verify a change

Run these checks from the repository root:

```sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=semaphoreui_mcp --cov-report=term-missing
UV_OFFLINE=true uv run --frozen semaphoreui-mcp --list-tools
uv run --frozen python -m build
```

Use `uv run --frozen ruff format .` to apply formatting. Add regression coverage
for changed behavior, especially request construction, argument validation,
authentication, and access restrictions. Documentation-only changes usually need
link and example checks rather than new tests.

For API compatibility changes, use the disposable integration test with Docker:

```sh
uv run --frozen python scripts/smoke_test.py --docker
uv run --frozen python scripts/smoke_test.py --docker \
  --image semaphoreui/semaphore:v2.18.31
```

The script creates and removes its own container and runs an Ansible debug task
inside it. It does not target your configured Semaphore instance. The first run
downloads the selected image. Record the exact image tag and result in the pull
request. The [compatibility reference](docs/api-coverage.md) describes the tested
workflows and their limits; a passing smoke test is not full API or Pro validation.

## API and dependency changes

Follow [catalogue maintenance](docs/catalogue-maintenance.md) for upstream schema,
route, or tool changes. Preserve tool names and existing argument contracts where
possible. Describe unavoidable breaking changes and migration steps explicitly.
Update user-facing examples when behavior or configuration changes.

For dependency changes, update `pyproject.toml` when the supported range changes,
regenerate `uv.lock` with `uv lock`, and include both affected files. Inspect the
resolved changes and run the checks above. Use `uv lock --upgrade-package NAME`
for a targeted upgrade instead of refreshing unrelated dependencies.

## Submit a pull request

Explain the problem, the resulting behavior, and how you verified it. Link the
relevant issue and mention any checks you could not run. Keep unrelated refactors
and dependency updates separate so reviewers can assess the change.

GitHub Actions runs lint, formatting, tests, packaging checks, and the compatibility
matrix. Fix failing checks before requesting a merge. Maintainers manage tagged
releases using the [release guide](docs/releasing.md).

Contributions are distributed under this repository's [MIT license](LICENSE).
Preserve the bundled Semaphore specification's attribution and
[upstream license](src/semaphoreui_mcp/data/SEMAPHORE-LICENSE); do not add proprietary
source, private API captures, or credentials to fixtures.
