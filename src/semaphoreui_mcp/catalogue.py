"""Compile the bundled upstream API into stable, validated MCP operations."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any
from urllib.parse import quote

import yaml


@dataclass(frozen=True)
class Operation:
  name: str
  method: str
  path: str
  description: str
  input_schema: dict[str, Any]
  read_only: bool
  query_parameters: tuple[str, ...] = ()
  body_default: Any = None
  body_path_fields: tuple[tuple[str, str], ...] = ()

  def prepare(self, arguments: dict[str, Any]) -> tuple[str, dict[str, Any], Any]:
    """Build a relative API request; the caller validates against input_schema."""
    path = self.path
    for name in re.findall(r"\{([^}]+)\}", path):
      value = str(arguments[name])
      # urllib leaves dot segments unescaped, so reject them before URL joining.
      if value in {".", ".."}:
        raise ValueError(f"Invalid path parameter: {name}")
      path = path.replace("{" + name + "}", quote(value, safe=""))
    params = {}
    for name in self.query_parameters:
      if name in arguments and arguments[name] is not None:
        value = arguments[name]
        params[name] = str(value).lower() if isinstance(value, bool) else value
    body = copy.deepcopy(arguments.get("body", self.body_default))
    if isinstance(body, dict):
      for field, parameter in self.body_path_fields:
        if field in body and body[field] != arguments[parameter]:
          raise ValueError(f"body.{field} must match {parameter}")
        body[field] = arguments[parameter]
    return path, params, body


def _normalize_schema(value: Any) -> Any:
  if isinstance(value, list):
    return [_normalize_schema(item) for item in value]
  if not isinstance(value, dict):
    return value
  result = {}
  for key, item in value.items():
    if key in {"x-nullable", "nullable", "x-example", "example", "readOnly"}:
      continue
    if key == "$ref":
      if not item.startswith("#/definitions/"):
        raise ValueError(f"Unsupported external schema reference: {item}")
      result[key] = item.replace("#/definitions/", "#/$defs/", 1)
    else:
      result[key] = _normalize_schema(item)
  if value.get("x-nullable") or value.get("nullable"):
    if "type" in result:
      types = result["type"] if isinstance(result["type"], list) else [result["type"]]
      result["type"] = list(dict.fromkeys([*types, "null"]))
    else:
      result = {"anyOf": [result, {"type": "null"}]}
  return result


def _reachable_definitions(schema: dict, definitions: dict) -> dict:
  selected = {}

  def visit(value: Any) -> None:
    if isinstance(value, list):
      for item in value:
        visit(item)
    elif isinstance(value, dict):
      reference = value.get("$ref")
      if reference:
        name = reference.removeprefix("#/$defs/")
        if name not in definitions:
          raise ValueError(f"Missing upstream schema definition: {name}")
        if name not in selected:
          selected[name] = definitions[name]
          visit(definitions[name])
      for item in value.values():
        visit(item)

  visit(schema)
  return dict(sorted(selected.items()))


def _path_schema(name: str, path: str) -> dict:
  if name in {"token_id", "role_slug", "app_id"} or (name == "alias_id" and "/terraform/" in path):
    return {"type": "string", "minLength": 1}
  return {"type": "integer", "minimum": 1}


def load_catalogue() -> dict[str, Operation]:
  """Load the vendored Swagger and audited route/schema corrections offline."""
  directory = files("semaphoreui_mcp").joinpath("data")
  spec = yaml.safe_load(directory.joinpath("api-docs.yaml").read_text())
  overrides = json.loads(directory.joinpath("overrides.json").read_text())
  definitions = spec["definitions"]
  for name, patch in overrides.get("definition_patches", {}).items():
    definition = definitions.setdefault(name, {"type": "object", "properties": {}})
    definition.setdefault("properties", {}).update(patch.get("properties", {}))
    definition.update({key: value for key, value in patch.items() if key != "properties"})
  definitions = _normalize_schema(definitions)
  entries = {}
  for original_path, path_item in spec["paths"].items():
    path = original_path.rstrip("/")
    path = path.replace("{api_token_id}", "{token_id}")
    path = path.replace("{extractvalue_id}", "{value_id}")
    if path == "/ws" or path.startswith("/auth/"):
      continue
    for method, endpoint in path_item.items():
      if method not in {"get", "post", "put", "delete", "patch"}:
        continue
      entry = copy.deepcopy(endpoint)
      entry.update(method=method.upper(), path=path)
      entry["parameters"] = [*path_item.get("parameters", []), *entry.get("parameters", [])]
      entries[f"{method.upper()} {path}"] = entry
  for endpoint in overrides["operations"]:
    key = f"{endpoint['method']} {endpoint['path']}"
    entries[key] = copy.deepcopy(endpoint)
  for key, patch in overrides.get("patches", {}).items():
    entries[key].update(copy.deepcopy(patch))

  catalogue = {}
  for key, endpoint in sorted(entries.items()):
    path = endpoint["path"]
    properties = {}
    required = []
    query_parameters = []
    for name in re.findall(r"\{([^}]+)\}", path):
      properties[name] = _path_schema(name, path)
      required.append(name)
    for parameter in endpoint.get("parameters", []):
      if "$ref" in parameter:
        parameter = spec["parameters"][parameter["$ref"].split("/")[-1]]
      if parameter["in"] == "body":
        properties["body"] = _normalize_schema(parameter["schema"])
        if parameter.get("required"):
          required.append("body")
      elif parameter["in"] == "query":
        name = parameter["name"]
        # This obsolete Swagger filter has no implementation in GetKeys.
        if name == "Key type":
          continue
        properties[name] = _normalize_schema(
          {
            k: v
            for k, v in parameter.items()
            if k not in {"name", "in", "required", "collectionFormat"}
          }
        )
        query_parameters.append(name)
    if "body" in endpoint:
      properties["body"] = _normalize_schema(endpoint["body"])
      if endpoint.get("body_required", True):
        required.append("body")
      else:
        required = [name for name in required if name != "body"]
    for name, schema in endpoint.get("query", {}).items():
      properties[name] = _normalize_schema(schema)
      if name not in query_parameters:
        query_parameters.append(name)
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
      schema["required"] = list(dict.fromkeys(required))
    reachable = _reachable_definitions(schema, definitions)
    if reachable:
      schema["$defs"] = reachable
    name = endpoint.get("name", overrides["names"].get(key))
    if not name or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
      raise ValueError(f"Missing or invalid operation name: {key}")
    if name in catalogue:
      raise ValueError(f"Duplicate operation name: {name}")
    description = endpoint.get("description") or endpoint.get("summary") or name.replace("_", " ")
    description = f"{description.strip().rstrip('.')}. {endpoint['method']} {path}."
    if "body" in properties:
      description += " Supply API fields in body; JSON-encoded string fields must remain strings."
    catalogue[name] = Operation(
      name=name,
      method=endpoint["method"],
      path=path,
      description=description,
      input_schema=schema,
      read_only=endpoint.get("read_only", endpoint["method"] == "GET"),
      query_parameters=tuple(query_parameters),
      body_default=endpoint.get("body_default"),
      body_path_fields=tuple(endpoint.get("body_path_fields", {}).items()),
    )
  return dict(sorted(catalogue.items()))
