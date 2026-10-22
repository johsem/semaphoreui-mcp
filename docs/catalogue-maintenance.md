# Maintaining the API catalogue

The catalogue is compiled offline at startup by
[`load_catalogue()`](../src/semaphoreui_mcp/catalogue.py). There is no separate
code-generation step or automatic download from the connected Semaphore server.
Changes to its source files change the advertised tools and their input schemas.

## Sources and responsibilities

| File | Role |
| --- | --- |
| `src/semaphoreui_mcp/data/api-docs.yaml` | Vendored Semaphore Swagger document, kept as upstream source. |
| `src/semaphoreui_mcp/data/overrides.json` | Audited route additions, stable names, request corrections, and source provenance. |
| `src/semaphoreui_mcp/catalogue.py` | Compilation, schema normalization, and request preparation. |
| `src/semaphoreui_mcp/server.py` | Tool exposure, access restrictions, and workflow helpers. |
| `src/semaphoreui_mcp/profiles.py` | Explicit membership of the optional core tool profile. |
| `docs/api-coverage.md` | Human-readable operation inventory, exclusions, and compatibility evidence. |

The current source release and its immutable GitHub links are recorded in
[API coverage](api-coverage.md) and the overrides' `upstream_version`/`source`
fields. The Swagger `info.version` can lag the source tag; do not treat it as a
runtime requirement or a detected server version.

The Swagger document alone is incomplete. Verify behavior against the same
upstream tag's `api/router.go`, public Go handlers and models, and web-client
requests. An HTTP route registered in Community source can still be a stub for a
licensed feature. Record evidence and limitations instead of inferring Pro
behavior from successful Community tests.

## Update process

1. Choose an exact upstream release tag or commit and review its changes relative
   to the currently recorded source. Keep links to the affected router, handler,
   model, and public UI code in the pull request. If replacing the vendored
   document, copy `api-docs.yml` from that revision to `data/api-docs.yaml` and
   update the provenance fields and source links together. Preserve its upstream
   content and license attribution; local corrections belong in overrides.
2. Audit additions, removals, aliases, changed field types, required fields,
   pagination, response formats, and task-status behavior. Recheck the exclusions
   in the coverage reference. Avoid exposing browser authentication flows,
   internal runner protocols, or duplicate route aliases as management tools.
3. Update `overrides.json`. `names` maps `METHOD /path` to stable tool names;
   `operations` supplies missing or replacement operation metadata;
   `patches` corrects existing operations; `definition_patches` updates shared
   schemas. Follow neighboring entries and the compiler's actual merge rules.
   Operation patches replace their named fields; definition patches merge
   `properties` but replace other supplied schema keys.
4. Review request safety as well as schema shape: path encoding, query fields,
   body defaults, path/body identifier consistency, read-only classification, and
   project scope. Verify new tools participate in the access restrictions. Decide
   explicitly whether a new operation belongs in the optional core profile and
   test both discovery and direct-call enforcement when changing profile coverage. Keep
   existing tool names and arguments stable when possible; explain breaking
   changes and migration steps explicitly.
5. Add focused regression tests in `tests/test_catalogue.py` and the relevant
   client/server tests. Include both accepted and rejected payloads for changed
   validation. Review inventory assertions deliberately when the operation set
   changes; do not change a count merely to silence a failure.
6. Update the operation table and request/edition notes in `api-coverage.md`.
   Update README examples if they are affected. Add compatibility results only
   after running the specified image, with the exact tag, date, and tested scope.
   Keep the CI compatibility matrix aligned with the releases it claims to test.

An additive upstream change can still require a catalogue update when an input
schema is strict. Older releases can lack a new route or field, and future
releases can change existing behavior. There is no blanket certification of past
or future versions. Separate source provenance, schema validation, live workflow
results, and edition coverage in documentation and release notes.

## Reproduce the inventory and verify documentation

After `uv sync --locked --group dev`, inspect the installed tools without network
access or Semaphore credentials:

```sh
UV_OFFLINE=true uv run --frozen semaphoreui-mcp --list-tools
```

To print the API operation table for the coverage reference, run this from the
repository root. Workflow helpers such as `wait_for_task` are intentionally not
part of this API-route table:

```sh
uv run --frozen python - <<'PY'
from semaphoreui_mcp.catalogue import load_catalogue

print("| Tool | Method | API path |")
print("| --- | --- | --- |")
for operation in load_catalogue().values():
  print(f"| `{operation.name}` | {operation.method} | `{operation.path}` |")
PY
```

Check that the documented rows match the compiled catalogue exactly:

```sh
uv run --frozen python - <<'PY'
import re
from pathlib import Path

from semaphoreui_mcp.catalogue import load_catalogue

reference = Path("docs/api-coverage.md").read_text()
documented = re.findall(r"^\| `([^`]+)` \| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)` \|$", reference, re.M)
actual = [(op.name, op.method, op.path) for op in load_catalogue().values()]
assert documented == actual, "Refresh the API coverage table from the compiled catalogue"
print("API coverage table matches the catalogue")
PY
```

Run the [contributor checks](../CONTRIBUTING.md#verify-a-change), then exercise
the affected release with `scripts/smoke_test.py --docker --image IMAGE`. Use a
disposable installation for additional endpoint checks. The existing smoke test
exercises core Community workflows; it does not validate every operation or
licensed feature. Report untested areas honestly.

Check the built wheel and source distribution still contain `api-docs.yaml`,
`overrides.json`, and `SEMAPHORE-LICENSE`. The vendored specification retains its
[upstream MIT license](../src/semaphoreui_mcp/data/SEMAPHORE-LICENSE). Document any
license change before accepting a new upstream source, and do not copy private
Pro implementation code into this project.
