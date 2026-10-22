import json
import re

import pytest
from jsonschema import Draft202012Validator, ValidationError

from semaphoreui_mcp.catalogue import load_catalogue


@pytest.fixture(scope="module")
def catalogue():
  return load_catalogue()


def validate(operation, arguments):
  Draft202012Validator(operation.input_schema).validate(arguments)


def test_all_management_operations_have_valid_self_contained_schemas(catalogue):
  assert len(catalogue) == 212
  assert len({(item.method, item.path) for item in catalogue.values()}) == 212
  for name, operation in catalogue.items():
    assert re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
    Draft202012Validator.check_schema(operation.input_schema)
    assert operation.input_schema["additionalProperties"] is False
    encoded = json.dumps(operation.input_schema)
    assert "#/definitions/" not in encoded
    assert "https://" not in encoded
    assert not operation.path.startswith(("/auth/", "/internal/", "/terraform/"))
    assert operation.path != "/ws"
  # Definitions are scoped to each operation, rather than copied wholesale.
  assert "$defs" not in catalogue["list_projects"].input_schema
  assert len(catalogue["create_template"].input_schema["$defs"]) < 15


def test_upstream_path_typos_are_corrected(catalogue):
  assert catalogue["get_current_user"].path == "/user"
  assert catalogue["get_project"].prepare({"project_id": 7})[0] == "/project/7"
  path, _, _ = catalogue["delete_api_token"].prepare({"token_id": "a/b?token"})
  assert path == "/user/tokens/a%2Fb%3Ftoken"
  assert catalogue["get_integration_value"].path.endswith("/values/{value_id}")


def test_path_segments_cannot_escape_api_root(catalogue):
  with pytest.raises(ValueError, match="path parameter"):
    catalogue["delete_api_token"].prepare({"token_id": ".."})


def test_optional_sorting_and_real_cursor_pagination(catalogue):
  validate(catalogue["list_templates"], {"project_id": 1})
  operation = catalogue["list_recent_tasks"]
  arguments = {"project_id": 4, "count": 50, "before": 102}
  validate(operation, arguments)
  assert operation.prepare(arguments) == (
    "/project/4/tasks/last",
    {"count": 50, "before": 102},
    None,
  )
  with pytest.raises(ValidationError):
    validate(operation, {"project_id": 4, "count": 201})
  with pytest.raises(ValidationError):
    validate(catalogue["get_task_output"], {"project_id": 4, "task_id": 2, "offset": 1})


def test_task_run_payload_matches_go_params(catalogue):
  operation = catalogue["create_task"]
  arguments = {
    "project_id": 3,
    "body": {
      "template_id": 8,
      "params": {"dry_run": True, "tags": ["deploy"], "limit": ["web01"]},
      "environment": '{"release":"v1"}',
      "arguments": '["--check"]',
    },
  }
  validate(operation, arguments)
  assert operation.prepare(arguments)[2] == arguments["body"]
  with pytest.raises(ValidationError):
    validate(operation, {"project_id": 3, "body": {}})
  with pytest.raises(ValidationError):
    validate(operation, {"project_id": 3, "body": {"template_id": 8, "environment": {}}})
  with pytest.raises(ValidationError):
    validate(operation, {"project_id": 3, "body": {"template_id": 8, "dry_run": True}})


def test_template_conditional_validation_and_nullable_fields(catalogue):
  operation = catalogue["create_template"]
  validate(
    operation,
    {
      "project_id": 1,
      "body": {"name": "Plan", "app": "tofu", "inventory_id": None, "vaults": None},
    },
  )
  with pytest.raises(ValidationError):
    validate(operation, {"project_id": 1, "body": {"name": "Deploy", "app": "ansible"}})
  validate(
    operation,
    {
      "project_id": 1,
      "body": {"name": "Deploy", "app": "ansible", "inventory_id": 2, "playbook": "site.yml"},
    },
  )
  validate(catalogue["create_project"], {"body": {"name": "Production", "alert_chat": None}})


def test_template_configuration_and_scheduled_run_params_have_different_shapes(catalogue):
  template_arguments = {
    "project_id": 1,
    "body": {
      "name": "Plan",
      "app": "tofu",
      "task_params": {"allow_destroy": True, "backend_filename": "backend.tf"},
      "survey_vars": [{"name": "release", "default_value": "stable"}],
    },
  }
  validate(catalogue["create_template"], template_arguments)
  template_arguments["body"]["task_params"]["allow_destroy"] = "true"
  with pytest.raises(ValidationError):
    validate(catalogue["create_template"], template_arguments)
  schedule = {
    "project_id": 1,
    "body": {
      "template_id": 2,
      "cron_format": "0 8 * * *",
      "delete_after_run": False,
      "task_params": {"git_branch": "main", "params": {"dry_run": True}},
    },
  }
  validate(catalogue["create_schedule"], schedule)
  schedule["body"]["task_params"]["params"]["dry_run"] = "true"
  with pytest.raises(ValidationError):
    validate(catalogue["create_schedule"], schedule)
  schedule["body"]["task_params"] = {"dry_run": True}
  with pytest.raises(ValidationError):
    validate(catalogue["create_schedule"], schedule)


def test_core_create_payloads_require_names(catalogue):
  for name in ["create_project", "create_template", "create_repository", "create_environment"]:
    operation = catalogue[name]
    arguments = {"body": {}}
    if "project_id" in operation.input_schema["properties"]:
      arguments["project_id"] = 1
    with pytest.raises(ValidationError):
      validate(operation, arguments)


def test_crud_fills_matching_path_identifiers_without_mutating_input(catalogue):
  operation = catalogue["update_inventory"]
  body = {"name": "Production", "type": "static", "ssh_key_id": None}
  arguments = {"project_id": 4, "inventory_id": 9, "body": body}
  validate(operation, arguments)
  assert operation.prepare(arguments)[2] == {**body, "project_id": 4, "id": 9}
  assert "project_id" not in body
  with pytest.raises(ValueError, match="must match"):
    operation.prepare({**arguments, "body": {**body, "project_id": 5}})


def test_stop_sends_empty_json_object_when_optional_body_is_omitted(catalogue):
  operation = catalogue["stop_task"]
  arguments = {"project_id": 1, "task_id": 2}
  validate(operation, arguments)
  assert operation.prepare(arguments)[2] == {}
  assert operation.read_only is False
  assert catalogue["validate_schedule"].read_only is True


def test_string_aliases_and_integer_totp_ids(catalogue):
  validate(
    catalogue["get_terraform_alias"],
    {
      "project_id": 1,
      "inventory_id": 2,
      "alias_id": "workspace-main",
    },
  )
  validate(catalogue["disable_user_totp"], {"user_id": 1, "totp_id": 3})
  with pytest.raises(ValidationError):
    validate(catalogue["disable_user_totp"], {"user_id": 1, "totp_id": "3"})


def test_catalogue_instances_do_not_share_mutable_schemas(catalogue):
  fresh = load_catalogue()
  fresh["create_project"].input_schema["properties"]["injected"] = {}
  assert "injected" not in catalogue["create_project"].input_schema["properties"]
