# Roadmap

## Initial release: Semaphore v2.19.17 management integration

- [x] Bundled, versioned API source and complete management-route catalogue.
- [x] Validated named tools for supported management operations.
- [x] Token/session authentication, TLS controls, timeouts, and useful errors.
- [x] Read-only mode and project allowlist enforcement.
- [x] Task wait helper, resources, and diagnostic prompts.
- [x] Stdio and authenticated Streamable HTTP transports.
- [x] Python package metadata, Docker/Compose, and GitLab CI configuration.
- [x] Setup, configuration, workflow, and compatibility documentation.
- [x] Automated verification and built distribution inspection.
- [x] Disposable Semaphore v2.19.17 Community integration smoke test.

## Compatibility and onboarding

- [x] Clarify source provenance versus runtime compatibility; remove promotional tool counts.
- [x] Verify core workflows on v2.18.31, v2.19.17, and v2.20.16-beta1 Community images.
- [x] Parameterize the smoke-test image and run the compatibility matrix in GitHub Actions.
- [x] Document source checkout and contribution/reporting steps; add package project URLs.

## Later candidates

These are possible follow-ups, not initial-release commitments:

- Expand compatibility coverage to more operations, releases, and editions.
- Versioned Python/container releases and release notes.
- Dedicated contribution guidance, issue forms, and a private vulnerability-reporting route.
- Dependency update automation and documented catalogue maintenance.
- Incremental catalogue updates as upstream routes and schemas change.
- Per-user upstream authorization if a multi-tenant deployment is required.
