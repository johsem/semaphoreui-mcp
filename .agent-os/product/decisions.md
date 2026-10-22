# Architecture decisions

## 2026-10-22: Record the upstream API source

Use Semaphore v2.19.17 as the source for the bundled schemas. Combine its published
API document with a reviewed management-route inventory because the document alone
does not describe every router endpoint. Bundle the source and catalogue so
startup and tool discovery work offline. Document explicit exclusions and edition
boundaries.
This source version is provenance, not a runtime restriction. Existing operations
can work across releases that retain their API contracts; record live smoke-test
results separately and do not promise universal backward or forward compatibility.

## 2026-10-22: Use named catalogue-driven tools

Generate the repetitive HTTP tools from normalized metadata and schemas. Keep
names stable and meaningful, and validate arguments before requesting upstream
resources. Add dedicated higher-level helpers only where they provide additional
behavior, such as bounded task polling.

## 2026-10-22: Use the official MCP SDK directly

The service is an MCP adapter, so the official SDK supplies the protocol and ASGI
transport. A separate application framework and persistence layer would duplicate
capabilities without satisfying an additional requirement. `httpx` owns the
upstream HTTP boundary.

## 2026-10-22: One configured Semaphore identity

Both transports act as a single configured account. Stdio is the default for local
clients. Streamable HTTP supports a separate shared bearer credential and requires
it when bound beyond loopback. DNS rebinding protection uses explicit host/origin
allowlists. Per-user OAuth delegation is outside this release.

## 2026-10-22: Enforce optional restrictions in the server

Read-only mode disables mutations and execution, rather than relying on a prompt
to discourage them. An optional project allowlist filters discovery and rejects
out-of-scope operations; global operations that cannot be restricted are denied
apart from safe information reads. Semaphore's own account permissions continue
to apply.

## 2026-10-22: Verify without live production credentials

Use mock HTTP boundaries and local MCP sessions for unit/protocol tests. Check
schema coverage, HTTP routing and authentication, resource/prompt behavior,
transport wiring, and restriction enforcement. An opt-in integration script
creates a disposable Semaphore Community container and runs a container-local
debug-only playbook. It does not use a configured production instance. Existing
deployments and Pro-only features require separate deployment-specific checks.
