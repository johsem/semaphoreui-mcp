import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/check_release.py"
SPEC = importlib.util.spec_from_file_location("check_release", SCRIPT)
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)


def git(root, *arguments):
  return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


@pytest.fixture
def repository(tmp_path):
  git(tmp_path, "init", "--initial-branch=main")
  git(tmp_path, "config", "user.name", "Release test")
  git(tmp_path, "config", "user.email", "release@example.invalid")
  (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
  module = tmp_path / "src/semaphoreui_mcp/__init__.py"
  module.parent.mkdir(parents=True)
  module.write_text('__version__ = "1.2.3"\n')
  git(tmp_path, "add", ".")
  git(tmp_path, "commit", "-m", "Initial version")
  git(tmp_path, "tag", "v1.2.3")
  return tmp_path


def test_accepts_tagged_main_commit_and_published_release(repository):
  result = release_check.check_release(
    repository,
    "v1.2.3",
    "main",
    {"tagName": "v1.2.3", "isDraft": False, "isPrerelease": False},
  )
  assert result == {
    "tag": "v1.2.3",
    "version": "1.2.3",
    "sha": git(repository, "rev-parse", "HEAD"),
  }


@pytest.mark.parametrize("tag", ["main", "--help", "v01.2.3", "v1.2.3\nsha=bad", "v1.2.3-beta1"])
def test_rejects_noncanonical_tags(repository, tag):
  with pytest.raises(ValueError, match="release tag"):
    release_check.check_release(repository, tag, "main")


@pytest.mark.parametrize("filename", ["pyproject.toml", "src/semaphoreui_mcp/__init__.py"])
def test_rejects_inconsistent_versions(repository, filename):
  path = repository / filename
  path.write_text(path.read_text().replace("1.2.3", "1.2.4"))
  with pytest.raises(ValueError, match="must match"):
    release_check.check_release(repository, "v1.2.3", "main")


def test_rejects_tag_not_merged_into_main(repository):
  git(repository, "checkout", "-b", "unmerged")
  git(repository, "commit", "--allow-empty", "-m", "Unmerged change")
  git(repository, "tag", "-f", "v1.2.3")
  with pytest.raises(ValueError, match="merged into main"):
    release_check.check_release(repository, "v1.2.3", "main")


def test_rejects_checkout_of_different_commit(repository):
  git(repository, "commit", "--allow-empty", "-m", "New change")
  with pytest.raises(ValueError, match="Check out the release tag"):
    release_check.check_release(repository, "v1.2.3", "main")


@pytest.mark.parametrize(
  "metadata",
  [
    {"tagName": "v1.2.4", "isDraft": False, "isPrerelease": False},
    {"tagName": "v1.2.3", "isDraft": True, "isPrerelease": False},
    {"tagName": "v1.2.3", "isDraft": False, "isPrerelease": True},
  ],
)
def test_rejects_mismatched_or_draft_release(repository, metadata):
  with pytest.raises(ValueError):
    release_check.check_release(repository, "v1.2.3", "main", metadata)


def test_accepts_annotated_prerelease_tag(repository):
  for filename in ["pyproject.toml", "src/semaphoreui_mcp/__init__.py"]:
    path = repository / filename
    path.write_text(path.read_text().replace("1.2.3", "1.2.4rc1"))
  git(repository, "add", ".")
  git(repository, "commit", "-m", "Release candidate")
  git(repository, "tag", "-a", "v1.2.4rc1", "-m", "Release candidate")
  result = release_check.check_release(
    repository,
    "v1.2.4rc1",
    "main",
    {"tagName": "v1.2.4rc1", "isDraft": False, "isPrerelease": True},
  )
  assert result["version"] == "1.2.4rc1"
