# Security policy

## Report a vulnerability privately

Use GitHub's [private vulnerability reporting form](https://github.com/johsem/semaphoreui-mcp/security/advisories/new)
for suspected authentication bypasses, access-control failures, credential leaks,
or other security vulnerabilities in this adapter. Sign in to GitHub to submit a
report. Do not disclose vulnerability details in a public issue or pull request.

Include the affected adapter version or commit, Semaphore version and edition,
transport, a minimal reproduction with synthetic data, and the security impact.
Describe relevant settings without including live tokens, passwords, private
keys, or sensitive task output. Use a disposable environment when reproducing a
problem.

Reports are handled on a best-effort basis; this project does not promise a
response deadline or a service-level agreement. Maintainers will use the private
report to discuss reproduction, a fix, and coordinated disclosure.

## Supported versions

Security fixes are developed on `main` and included in a release when ready. Use
the latest available release. Older releases do not have a separate backport or
security-maintenance commitment. Before the first release, use the latest `main`
commit. Dependencies and the connected Semaphore installation also need to be
maintained by the deployment operator.

## Deployment boundaries

Both transports use one configured Semaphore identity. Everyone who can access
the MCP server can act within that identity's permissions and the adapter's
configured restrictions. The shared HTTP bearer token does not provide per-user
delegation or separate Semaphore identities.

Use a dedicated Semaphore account with only the required permissions. Where
appropriate, enable `SEMAPHORE_READ_ONLY` and restrict `SEMAPHORE_PROJECT_IDS`.
Read-only access still exposes permitted upstream data, including potentially
sensitive task logs and variables; it is not a redaction mechanism.

For network access, set a strong `MCP_HTTP_TOKEN`, use TLS at a trusted reverse
proxy, and configure the documented host/origin allowlists. Keep upstream TLS
verification enabled and use a private CA bundle when needed. Keep credentials
out of repository files, public logs, screenshots, and issue reports.

See the [README](README.md#configuration) for configuration and deployment details.
For vulnerabilities in Semaphore itself, use the
[upstream project's security policy](https://github.com/semaphoreui/semaphore/security/policy).
