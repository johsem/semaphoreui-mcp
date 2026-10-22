# Semaphore API coverage

This server exposes **212 management operations** pinned to Semaphore UI **v2.19.17**. The bundled [upstream Swagger specification](https://github.com/semaphoreui/semaphore/blob/v2.19.17/api-docs.yml) supplies 121 management operations. An audit of the [release router](https://github.com/semaphoreui/semaphore/blob/v2.19.17/api/router.go), public Go handlers/models, and web UI adds 91 operations and corrects stale paths, parameters, and schemas in `data/overrides.json`.

The Swagger document's internal `info.version` still says `2.16.14`; the vendored file is from the `v2.19.17` Git tag. Coverage describes registered routes and request construction. It does not certify every endpoint against a running installation or guarantee availability across older releases, editions, licenses, and user permissions.

## Included capabilities

- Projects, backup/restore, membership, permissions, events, notifications, and cache maintenance.
- Templates, surveys, multiple variable groups, inventory attachments, permission overrides, task settings, container images, and JWT settings.
- Task execution, cancellation, approval/rejection, structured/plain logs, stages, Ansible hosts/errors, history, and statistics.
- Inventories including Terraform/OpenTofu/Terragrunt workspaces, repositories and branch/playbook discovery, variable groups, access keys, secret storage, and synchronization.
- Cron and one-time schedules, views and ordering, integration configuration, aliases, matchers, and extracted values.
- Global/project runners, tags, activation, registration tokens, and cache maintenance.
- Users, API tokens, preferences, TOTP enrollment, administrative options, applications, cluster inspection/maintenance, and subscription management.
- Edition-dependent workflows, runs, approvals, artifacts, roles, and Terraform state/alias management.

## Request conventions and corrections

Path and query parameters are top-level tool arguments; JSON API payloads use `body`. Paths are relative to the configured `/api` base. Core CRUD operations fill the known duplicate `body.project_id`, `body.id`, and integration identifiers from path arguments; conflicting identifiers are rejected. Updates send the supplied object with these identifiers, not an implicit read/merge/write; supply the complete object expected by upstream.

Top-level arguments are strict, so misspelled argument names fail validation. Body schemas generally allow extension fields for new server versions and Pro features. Task creation and saved task parameter wrappers are strict to reject misplaced execution flags such as `body.dry_run`; application-specific `params` objects remain extensible. Referenced definitions are included only when needed by that operation. Swagger `x-nullable` is converted to JSON Schema nullability, and known optional IDs are nullable.

Corrections include trailing-slash removal, `token_id` and `value_id` route names, optional sorting parameters, removal of the unimplemented `Key type` filter, string Terraform aliases, and integer TOTP IDs. The obsolete task execution booleans are replaced by discoverable `body.params` options. Template configuration uses `body.task_params.allow_*` switches; schedule and integration execution options use `body.task_params.params`. Variable group `json`/`env`, task `environment`, and command `arguments` remain JSON-encoded **strings**, as required by Semaphore. Template survey defaults, schedule repository/delete-after-run options, secret-source fields, and newer inventory types are included.

The source of required fields and conditional checks is the public Go models and validation. For example, task creation requires `template_id`, Ansible templates require an inventory, and non-Terraform templates require a playbook. The upstream API remains authoritative for resource relationships and version-specific validation.

## History, logs, and execution status

`list_recent_tasks` and `list_recent_template_tasks` support `count` (1–200) and `before` (the last task ID from the previous page). MCP results contain the records rather than upstream HTTP headers; keep requesting pages with the last task ID until an empty page is returned. The legacy `limit` parameter is supported. `list_tasks` and `list_template_tasks` return at most 1000 tasks and do not accept offset pagination.

`get_task_output` returns all persisted structured log entries. `get_task_raw_output` returns plain text with ANSI escapes removed. Neither output endpoint supports pagination in this release. Statistics accept `start`/`end` as `YYYY-MM-DD`, plus an optional user ID.

Only `success`, `error`, and `stopped` are terminal task statuses. `waiting_confirmation` requires a decision; `confirmed` and `rejected` are transitional states, alongside `waiting`, `starting`, `running`, and `stopping`. These semantics come from the upstream [task status implementation](https://github.com/semaphoreui/semaphore/blob/v2.19.17/pkg/task_logger/task_logger.go).

One upstream quirk is preserved and documented: `GET /tasks/{task_id}` currently returns the global task pool. Use project-scoped `get_task` for an individual task.

## Edition limits and exclusions

The public Community source registers several Pro routes but implements them as empty lists or HTTP 404 responses. Roles, workflows, subscription operations, project runners, and Terraform state features may require an appropriate edition/license. Request fields for private Pro implementations are based on the published Swagger, public model types, and the public web client's requests; additional body fields remain accepted. No Pro instance was used for validation.

The following are intentionally outside the management tool catalogue:

- Login/logout and verification/recovery routes: authentication belongs to the HTTP client configuration/session lifecycle.
- OIDC browser redirects and public JWKS discovery.
- WebSocket streaming; ordinary REST event history and task logs are included.
- Internal runner registration/polling protocol; global and project runner administration is included.
- Incoming integration webhooks and the Terraform HTTP backend GET/POST/LOCK/UNLOCK protocol; integration administration and project Terraform state reads/deletes are included.
- HEAD/OPTIONS aliases and duplicate POST aliases for PUT updates. Each semantic management operation is exposed once.

## Operation reference

The following table is the complete API operation catalogue. Workflow helpers, resources, and prompts provided by the MCP server are additional conveniences and are not counted here.

| Tool | Method | API path |
| --- | --- | --- |
| `activate_subscription` | POST | `/subscription` |
| `attach_template_inventory` | POST | `/project/{project_id}/templates/{template_id}/inventory/{inventory_id}/attach` |
| `clear_cluster_tasks` | DELETE | `/cluster/tasks` |
| `clear_global_runner_cache` | DELETE | `/runners/{runner_id}/cache` |
| `clear_project_cache` | DELETE | `/project/{project_id}/cache` |
| `clear_project_runner_cache` | DELETE | `/project/{project_id}/runners/{runner_id}/cache` |
| `clear_server_cache` | DELETE | `/cache` |
| `confirm_task` | POST | `/project/{project_id}/tasks/{task_id}/confirm` |
| `create_access_key` | POST | `/project/{project_id}/keys` |
| `create_api_token` | POST | `/user/tokens` |
| `create_environment` | POST | `/project/{project_id}/environment` |
| `create_global_role` | POST | `/roles` |
| `create_global_runner` | POST | `/runners` |
| `create_integration` | POST | `/project/{project_id}/integrations` |
| `create_integration_alias` | POST | `/project/{project_id}/integrations/{integration_id}/aliases` |
| `create_integration_matcher` | POST | `/project/{project_id}/integrations/{integration_id}/matchers` |
| `create_integration_value` | POST | `/project/{project_id}/integrations/{integration_id}/values` |
| `create_inventory` | POST | `/project/{project_id}/inventory` |
| `create_project` | POST | `/projects` |
| `create_project_integration_alias` | POST | `/project/{project_id}/integrations/aliases` |
| `create_project_role` | POST | `/project/{project_id}/roles` |
| `create_project_runner` | POST | `/project/{project_id}/runners` |
| `create_project_user` | POST | `/project/{project_id}/users` |
| `create_repository` | POST | `/project/{project_id}/repositories` |
| `create_schedule` | POST | `/project/{project_id}/schedules` |
| `create_secret_storage` | POST | `/project/{project_id}/secret_storages` |
| `create_task` | POST | `/project/{project_id}/tasks` |
| `create_template` | POST | `/project/{project_id}/templates` |
| `create_template_permission` | POST | `/project/{project_id}/templates/{template_id}/perms` |
| `create_terraform_alias` | POST | `/project/{project_id}/inventory/{inventory_id}/terraform/aliases` |
| `create_user` | POST | `/users` |
| `create_view` | POST | `/project/{project_id}/views` |
| `create_workflow` | POST | `/project/{project_id}/workflows` |
| `delete_access_key` | DELETE | `/project/{project_id}/keys/{key_id}` |
| `delete_api_token` | DELETE | `/user/tokens/{token_id}` |
| `delete_app` | DELETE | `/apps/{app_id}` |
| `delete_environment` | DELETE | `/project/{project_id}/environment/{environment_id}` |
| `delete_global_role` | DELETE | `/roles/{role_slug}` |
| `delete_global_runner` | DELETE | `/runners/{runner_id}` |
| `delete_global_task` | DELETE | `/tasks/{task_id}` |
| `delete_integration` | DELETE | `/project/{project_id}/integrations/{integration_id}` |
| `delete_integration_alias` | DELETE | `/project/{project_id}/integrations/{integration_id}/aliases/{alias_id}` |
| `delete_integration_matcher` | DELETE | `/project/{project_id}/integrations/{integration_id}/matchers/{matcher_id}` |
| `delete_integration_value` | DELETE | `/project/{project_id}/integrations/{integration_id}/values/{value_id}` |
| `delete_inventory` | DELETE | `/project/{project_id}/inventory/{inventory_id}` |
| `delete_project` | DELETE | `/project/{project_id}` |
| `delete_project_integration_alias` | DELETE | `/project/{project_id}/integrations/aliases/{alias_id}` |
| `delete_project_role` | DELETE | `/project/{project_id}/roles/{role_slug}` |
| `delete_project_runner` | DELETE | `/project/{project_id}/runners/{runner_id}` |
| `delete_project_user` | DELETE | `/project/{project_id}/users/{user_id}` |
| `delete_repository` | DELETE | `/project/{project_id}/repositories/{repository_id}` |
| `delete_schedule` | DELETE | `/project/{project_id}/schedules/{schedule_id}` |
| `delete_secret_storage` | DELETE | `/project/{project_id}/secret_storages/{storage_id}` |
| `delete_subscription` | DELETE | `/subscription` |
| `delete_task` | DELETE | `/project/{project_id}/tasks/{task_id}` |
| `delete_template` | DELETE | `/project/{project_id}/templates/{template_id}` |
| `delete_template_permission` | DELETE | `/project/{project_id}/templates/{template_id}/perms/{perm_id}` |
| `delete_terraform_alias` | DELETE | `/project/{project_id}/inventory/{inventory_id}/terraform/aliases/{alias_id}` |
| `delete_terraform_state` | DELETE | `/project/{project_id}/inventory/{inventory_id}/terraform/states/{state_id}` |
| `delete_user` | DELETE | `/users/{user_id}` |
| `delete_view` | DELETE | `/project/{project_id}/views/{view_id}` |
| `delete_workflow` | DELETE | `/project/{project_id}/workflows/{workflow_id}` |
| `detach_template_inventory` | POST | `/project/{project_id}/templates/{template_id}/inventory/{inventory_id}/detach` |
| `disable_user_totp` | DELETE | `/users/{user_id}/2fas/totp/{totp_id}` |
| `enable_user_totp` | POST | `/users/{user_id}/2fas/totp` |
| `get_access_key` | GET | `/project/{project_id}/keys/{key_id}` |
| `get_access_key_references` | GET | `/project/{project_id}/keys/{key_id}/refs` |
| `get_admin_info` | GET | `/admin/info` |
| `get_app` | GET | `/apps/{app_id}` |
| `get_cluster_status` | GET | `/cluster` |
| `get_current_user` | GET | `/user` |
| `get_environment` | GET | `/project/{project_id}/environment/{environment_id}` |
| `get_environment_references` | GET | `/project/{project_id}/environment/{environment_id}/refs` |
| `get_global_role` | GET | `/roles/{role_slug}` |
| `get_global_runner` | GET | `/runners/{runner_id}` |
| `get_global_task` | GET | `/tasks/{task_id}` |
| `get_integration` | GET | `/project/{project_id}/integrations/{integration_id}` |
| `get_integration_matcher` | GET | `/project/{project_id}/integrations/{integration_id}/matchers/{matcher_id}` |
| `get_integration_matcher_references` | GET | `/project/{project_id}/integrations/{integration_id}/matchers/{matcher_id}/refs` |
| `get_integration_references` | GET | `/project/{project_id}/integrations/{integration_id}/refs` |
| `get_integration_value` | GET | `/project/{project_id}/integrations/{integration_id}/values/{value_id}` |
| `get_integration_value_references` | GET | `/project/{project_id}/integrations/{integration_id}/values/{value_id}/refs` |
| `get_inventory` | GET | `/project/{project_id}/inventory/{inventory_id}` |
| `get_inventory_references` | GET | `/project/{project_id}/inventory/{inventory_id}/refs` |
| `get_latest_terraform_state` | GET | `/project/{project_id}/inventory/{inventory_id}/terraform/states/latest` |
| `get_project` | GET | `/project/{project_id}` |
| `get_project_backup` | GET | `/project/{project_id}/backup` |
| `get_project_permissions` | GET | `/project/{project_id}/role` |
| `get_project_role` | GET | `/project/{project_id}/roles/{role_slug}` |
| `get_project_runner` | GET | `/project/{project_id}/runners/{runner_id}` |
| `get_project_task_stats` | GET | `/project/{project_id}/stats` |
| `get_project_user` | GET | `/project/{project_id}/users/{user_id}` |
| `get_repository` | GET | `/project/{project_id}/repositories/{repository_id}` |
| `get_repository_references` | GET | `/project/{project_id}/repositories/{repository_id}/refs` |
| `get_schedule` | GET | `/project/{project_id}/schedules/{schedule_id}` |
| `get_secret_storage` | GET | `/project/{project_id}/secret_storages/{storage_id}` |
| `get_secret_storage_references` | GET | `/project/{project_id}/secret_storages/{storage_id}/refs` |
| `get_server_options` | GET | `/options` |
| `get_subscription` | GET | `/subscription` |
| `get_system_info` | GET | `/info` |
| `get_task` | GET | `/project/{project_id}/tasks/{task_id}` |
| `get_task_output` | GET | `/project/{project_id}/tasks/{task_id}/output` |
| `get_task_raw_output` | GET | `/project/{project_id}/tasks/{task_id}/raw_output` |
| `get_template` | GET | `/project/{project_id}/templates/{template_id}` |
| `get_template_permission` | GET | `/project/{project_id}/templates/{template_id}/perms/{perm_id}` |
| `get_template_references` | GET | `/project/{project_id}/templates/{template_id}/refs` |
| `get_template_task_stats` | GET | `/project/{project_id}/templates/{template_id}/stats` |
| `get_terraform_alias` | GET | `/project/{project_id}/inventory/{inventory_id}/terraform/aliases/{alias_id}` |
| `get_terraform_state` | GET | `/project/{project_id}/inventory/{inventory_id}/terraform/states/{state_id}` |
| `get_user` | GET | `/users/{user_id}` |
| `get_user_options` | GET | `/user/options` |
| `get_user_totp_qr` | GET | `/users/{user_id}/2fas/totp/{totp_id}/qr` |
| `get_view` | GET | `/project/{project_id}/views/{view_id}` |
| `get_workflow` | GET | `/project/{project_id}/workflows/{workflow_id}` |
| `get_workflow_run` | GET | `/project/{project_id}/workflows/{workflow_id}/runs/{run_id}` |
| `get_workflow_run_artifacts` | GET | `/project/{project_id}/workflows/{workflow_id}/runs/{run_id}/artifacts` |
| `leave_project` | DELETE | `/project/{project_id}/me` |
| `list_access_keys` | GET | `/project/{project_id}/keys` |
| `list_api_tokens` | GET | `/user/tokens` |
| `list_apps` | GET | `/apps` |
| `list_available_project_roles` | GET | `/project/{project_id}/roles/all` |
| `list_cluster_tasks` | GET | `/cluster/tasks` |
| `list_environments` | GET | `/project/{project_id}/environment` |
| `list_events` | GET | `/events` |
| `list_global_roles` | GET | `/roles` |
| `list_global_runner_tags` | GET | `/runner_tags` |
| `list_global_runners` | GET | `/runners` |
| `list_global_tasks` | GET | `/tasks` |
| `list_integration_aliases` | GET | `/project/{project_id}/integrations/{integration_id}/aliases` |
| `list_integration_matchers` | GET | `/project/{project_id}/integrations/{integration_id}/matchers` |
| `list_integration_values` | GET | `/project/{project_id}/integrations/{integration_id}/values` |
| `list_integrations` | GET | `/project/{project_id}/integrations` |
| `list_inventories` | GET | `/project/{project_id}/inventory` |
| `list_project_events` | GET | `/project/{project_id}/events` |
| `list_project_integration_aliases` | GET | `/project/{project_id}/integrations/aliases` |
| `list_project_roles` | GET | `/project/{project_id}/roles` |
| `list_project_runner_tags` | GET | `/project/{project_id}/runner_tags` |
| `list_project_runners` | GET | `/project/{project_id}/runners` |
| `list_project_users` | GET | `/project/{project_id}/users` |
| `list_projects` | GET | `/projects` |
| `list_recent_events` | GET | `/events/last` |
| `list_recent_project_events` | GET | `/project/{project_id}/events/last` |
| `list_recent_tasks` | GET | `/project/{project_id}/tasks/last` |
| `list_recent_template_tasks` | GET | `/project/{project_id}/templates/{template_id}/tasks/last` |
| `list_repositories` | GET | `/project/{project_id}/repositories` |
| `list_repository_branches` | GET | `/project/{project_id}/repositories/{repository_id}/branches` |
| `list_repository_playbooks` | GET | `/project/{project_id}/repositories/{repository_id}/playbooks` |
| `list_schedules` | GET | `/project/{project_id}/schedules` |
| `list_secret_storages` | GET | `/project/{project_id}/secret_storages` |
| `list_task_ansible_errors` | GET | `/project/{project_id}/tasks/{task_id}/ansible/errors` |
| `list_task_ansible_hosts` | GET | `/project/{project_id}/tasks/{task_id}/ansible/hosts` |
| `list_task_stages` | GET | `/project/{project_id}/tasks/{task_id}/stages` |
| `list_tasks` | GET | `/project/{project_id}/tasks` |
| `list_template_permissions` | GET | `/project/{project_id}/templates/{template_id}/perms` |
| `list_template_schedules` | GET | `/project/{project_id}/templates/{template_id}/schedules` |
| `list_template_tasks` | GET | `/project/{project_id}/templates/{template_id}/tasks` |
| `list_templates` | GET | `/project/{project_id}/templates` |
| `list_terraform_aliases` | GET | `/project/{project_id}/inventory/{inventory_id}/terraform/aliases` |
| `list_terraform_states` | GET | `/project/{project_id}/inventory/{inventory_id}/terraform/states` |
| `list_users` | GET | `/users` |
| `list_view_templates` | GET | `/project/{project_id}/views/{view_id}/templates` |
| `list_views` | GET | `/project/{project_id}/views` |
| `list_workflow_run_approvals` | GET | `/project/{project_id}/workflows/{workflow_id}/runs/{run_id}/approvals` |
| `list_workflow_runs` | GET | `/project/{project_id}/workflows/{workflow_id}/runs` |
| `list_workflows` | GET | `/project/{project_id}/workflows` |
| `ping` | GET | `/ping` |
| `refresh_subscription` | POST | `/subscription/refresh` |
| `regenerate_global_runner_registration_token` | POST | `/runners/{runner_id}/registration-token` |
| `regenerate_project_runner_registration_token` | POST | `/project/{project_id}/runners/{runner_id}/registration-token` |
| `reject_task` | POST | `/project/{project_id}/tasks/{task_id}/reject` |
| `resolve_workflow_approval` | POST | `/project/{project_id}/workflows/{workflow_id}/runs/{run_id}/approvals/{node_id}` |
| `restore_project` | POST | `/projects/restore` |
| `run_workflow` | POST | `/project/{project_id}/workflows/{workflow_id}/run` |
| `set_app_active` | POST | `/apps/{app_id}/active` |
| `set_global_runner_active` | POST | `/runners/{runner_id}/active` |
| `set_project_runner_active` | POST | `/project/{project_id}/runners/{runner_id}/active` |
| `set_schedule_active` | PUT | `/project/{project_id}/schedules/{schedule_id}/active` |
| `set_server_option` | POST | `/options` |
| `set_template_default_inventory` | POST | `/project/{project_id}/templates/{template_id}/inventory/{inventory_id}/set_default` |
| `set_user_option` | POST | `/user/options` |
| `set_view_positions` | POST | `/project/{project_id}/views/positions` |
| `stop_task` | POST | `/project/{project_id}/tasks/{task_id}/stop` |
| `stop_template_tasks` | POST | `/project/{project_id}/templates/{template_id}/stop_all_tasks` |
| `stop_workflow_run` | POST | `/project/{project_id}/workflows/{workflow_id}/runs/{run_id}/stop` |
| `sync_environment` | POST | `/project/{project_id}/environment/{environment_id}/sync` |
| `sync_secret_storage` | POST | `/project/{project_id}/secret_storages/{storage_id}/sync` |
| `test_project_notification` | POST | `/project/{project_id}/notifications/test` |
| `update_access_key` | PUT | `/project/{project_id}/keys/{key_id}` |
| `update_app` | PUT | `/apps/{app_id}` |
| `update_environment` | PUT | `/project/{project_id}/environment/{environment_id}` |
| `update_global_role` | PUT | `/roles/{role_slug}` |
| `update_global_runner` | PUT | `/runners/{runner_id}` |
| `update_integration` | PUT | `/project/{project_id}/integrations/{integration_id}` |
| `update_integration_matcher` | PUT | `/project/{project_id}/integrations/{integration_id}/matchers/{matcher_id}` |
| `update_integration_value` | PUT | `/project/{project_id}/integrations/{integration_id}/values/{value_id}` |
| `update_inventory` | PUT | `/project/{project_id}/inventory/{inventory_id}` |
| `update_project` | PUT | `/project/{project_id}` |
| `update_project_role` | PUT | `/project/{project_id}/roles/{role_slug}` |
| `update_project_runner` | PUT | `/project/{project_id}/runners/{runner_id}` |
| `update_project_user` | PUT | `/project/{project_id}/users/{user_id}` |
| `update_repository` | PUT | `/project/{project_id}/repositories/{repository_id}` |
| `update_schedule` | PUT | `/project/{project_id}/schedules/{schedule_id}` |
| `update_secret_storage` | PUT | `/project/{project_id}/secret_storages/{storage_id}` |
| `update_template` | PUT | `/project/{project_id}/templates/{template_id}` |
| `update_template_description` | PUT | `/project/{project_id}/templates/{template_id}/description` |
| `update_template_permission` | PUT | `/project/{project_id}/templates/{template_id}/perms/{perm_id}` |
| `update_terraform_alias` | PUT | `/project/{project_id}/inventory/{inventory_id}/terraform/aliases/{alias_id}` |
| `update_user` | PUT | `/users/{user_id}` |
| `update_user_password` | POST | `/users/{user_id}/password` |
| `update_view` | PUT | `/project/{project_id}/views/{view_id}` |
| `update_workflow` | PUT | `/project/{project_id}/workflows/{workflow_id}` |
| `validate_schedule` | POST | `/project/{project_id}/schedules/validate` |
