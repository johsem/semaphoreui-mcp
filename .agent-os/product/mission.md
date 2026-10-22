# Product mission

Semaphore UI MCP gives MCP-compatible assistants a complete, discoverable
management interface to Semaphore UI automation. Operators can inspect project
configuration, administer resources, run tasks, and diagnose failures without
translating each action into a raw HTTP request.

The server uses Semaphore's management API across compatible releases. It serves
a single configured Semaphore identity through local stdio or authenticated
Streamable HTTP, and can restrict that identity further through read-only mode and
a project allowlist.

Success means explicit API coverage, accurate tool schemas, useful errors, bounded
network behavior, reproducible packaging, and validation that never requires
executing jobs against a production Semaphore instance.

Interactive SSO, browser UI automation, runner transport, incoming webhooks, and
Terraform backend transport are outside the MCP management interface. The server
does not create a new authorization system or grant access beyond the configured
Semaphore account.
