"""Check that a release names the tested package and a commit merged into main."""

import argparse
import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

RELEASE_TAG = re.compile(r"v((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:(a|b|rc)\d+)?)")


def git(root: Path, *arguments: str) -> str:
  return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def check_release(
  root: Path, tag: str, main_ref: str, release: dict | None = None
) -> dict[str, str]:
  match = RELEASE_TAG.fullmatch(tag)
  if not match:
    raise ValueError("Use a release tag such as v1.2.3 or v1.2.3rc1")
  version = match[1]
  project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
  module = ast.parse((root / "src/semaphoreui_mcp/__init__.py").read_text())
  runtime_version = next(
    (
      ast.literal_eval(statement.value)
      for statement in module.body
      if isinstance(statement, ast.Assign)
      and any(
        isinstance(target, ast.Name) and target.id == "__version__" for target in statement.targets
      )
    ),
    None,
  )
  if project["version"] != version or runtime_version != version:
    raise ValueError("Tag, pyproject.toml version and runtime __version__ must match")

  commit = git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}")
  if commit != git(root, "rev-parse", "HEAD"):
    raise ValueError("Check out the release tag before validating it")
  ancestor = subprocess.run(
    ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, main_ref],
    check=False,
  )
  if ancestor.returncode:
    raise ValueError("Release commit must already be merged into main")

  prerelease = match[2] is not None
  if release is not None:
    if release.get("tagName") != tag or release.get("isDraft") is not False:
      raise ValueError("An existing published GitHub release is required")
    if release.get("isPrerelease") != prerelease:
      raise ValueError("GitHub prerelease status must match the version suffix")
  return {"tag": tag, "version": version, "sha": commit}


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--tag", required=True)
  parser.add_argument("--root", type=Path, default=Path.cwd())
  parser.add_argument("--main-ref", default="refs/remotes/origin/main")
  parser.add_argument("--release-json", type=Path)
  parser.add_argument("--github-output", type=Path)
  arguments = parser.parse_args()
  release = json.loads(arguments.release_json.read_text()) if arguments.release_json else None
  try:
    result = check_release(arguments.root, arguments.tag, arguments.main_ref, release)
  except (ValueError, subprocess.CalledProcessError) as error:
    parser.error(str(error))
  print(json.dumps(result))
  if arguments.github_output:
    with arguments.github_output.open("a") as output:
      output.write("".join(f"{key}={value}\n" for key, value in result.items()))


if __name__ == "__main__":
  main()
