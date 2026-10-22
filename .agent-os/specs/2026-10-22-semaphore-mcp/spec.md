# Semaphore UI MCP integration

Date: 2026-10-22

## Objective

Build a full-featured Model Context Protocol server for the Semaphore UI management
API, with a pinned and auditable compatibility boundary, safe configuration, and
documented self-hosting paths.

## Functional requirements

1. Expose named tools for supported management endpoints in Semaphore v2.19.17,
   including routes omitted from the upstream OpenAPI document.
2. Validate path, query, and JSON-body inputs through each tool's advertised schema.
3. Support Semaphore API-token authentication and username/password session login.
4. Support custom CA certificates, configurable TLS verification, upstream timeout
   limits, and structured, credential-safe failures.
5. Enforce read-only mode and optional project restrictions across tools/resources.
6. Provide a bounded `wait_for_task` operation alongside task status and output APIs.
7. Provide project/task resources and prompts for task diagnosis and run planning.
8. Run over stdio by default and stateless Streamable HTTP at `/mcp` when selected.
9. Require a separate HTTP bearer token on non-loopback binds and support host and
   origin allowlists.
10. Provide offline catalogue listing, a version command, installable distribution,
    container configuration, CI, and end-user documentation.

## Scope boundaries

Management routes are in scope, including edition-specific routes when upstream
permissions permit them. Interactive SSO redirects, WebSockets, runner agent
protocols, incoming integration webhooks, Terraform backend transport, and JWKS are
excluded. Login/session setup is performed internally rather than as a general
assistant tool. The coverage reference records the precise route boundary.

The HTTP deployment represents one Semaphore account and uses a shared MCP bearer
token. Per-user OAuth, persistent MCP application storage, and deployment into a
user-provided production environment are not required for the initial release.

## Validation

- Verify catalogue/schema coverage against the pinned upstream API and route data.
- Exercise request construction, token/session behavior, error handling, TLS and
  configuration validation with controlled HTTP responses.
- Exercise read-only/project restrictions, helper polling, resources and prompts.
- Complete a local MCP initialization, tool discovery, and representative calls.
- Verify HTTP token enforcement and host restrictions, including non-loopback
  startup validation.
- Run Ruff and the test suite; build wheel/source distributions and inspect bundled
  API data, attribution, and entry points.
- Run the opt-in integration smoke test against a disposable Semaphore v2.19.17
  Community container, including a container-local debug-only Ansible task.
- Document that deployment-specific policies, external runner connectivity, and
  Pro-only routes require validation against the intended deployment.
