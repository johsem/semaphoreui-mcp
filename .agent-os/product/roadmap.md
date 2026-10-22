# Roadmap

## Initial release: Semaphore v2.19.17 management integration

- [x] Version-pinned API source and complete management-route catalogue.
- [x] Validated named tools for supported management operations.
- [x] Token/session authentication, TLS controls, timeouts, and useful errors.
- [x] Read-only mode and project allowlist enforcement.
- [x] Task wait helper, resources, and diagnostic prompts.
- [x] Stdio and authenticated Streamable HTTP transports.
- [x] Python package metadata, Docker/Compose, and GitLab CI configuration.
- [x] Setup, configuration, workflow, and compatibility documentation.
- [x] Automated verification and built distribution inspection.
- [x] Disposable Semaphore v2.19.17 Community integration smoke test.

## Later candidates

These are possible follow-ups, not initial-release commitments:

- Compatibility matrices and regression tests against multiple live Semaphore
  versions and editions.
- Incremental catalogue updates as upstream routes and schemas change.
- Per-user upstream authorization if a multi-tenant deployment is required.
