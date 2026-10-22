# Releases and distribution

The release workflow publishes a wheel, source distribution and `SHA256SUMS` to a
GitHub release, builds `linux/amd64` and `linux/arm64` images in GHCR, and can publish
the Python package to PyPI through Trusted Publishing. These are publishing
capabilities; adding the workflow does not create a release or a PyPI package.

## One-time maintainer setup

1. Create the GitHub Actions environment named **`pypi`**. Consider adding a required
   reviewer. If deployment branches/tags are restricted, allow the `main` branch
   for manual retries and tags matching `v*` for release-triggered runs.
2. In your [PyPI publishing settings](https://pypi.org/manage/account/publishing/),
   add a pending GitHub publisher with these exact fields:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `semaphoreui-mcp` |
   | GitHub owner | `johsem` |
   | GitHub repository | `semaphoreui-mcp` |
   | Workflow filename | `release.yml` |
   | Environment name | `pypi` |

   If the project already exists under your account, add the publisher in that
   project's Publishing settings instead. A pending publisher does not reserve
   the project name. The first successful publish creates the project. See the
   [PyPI setup documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
3. After registering the publisher, enable the repository Actions variable:

   ```sh
   gh variable set PYPI_PUBLISH_ENABLED --body true --repo johsem/semaphoreui-mcp
   ```

   This gate is off by default so GitHub assets and containers can ship while
   PyPI account setup is incomplete. A skipped PyPI job means **not published to
   PyPI**. The workflow summary reports each destination separately.
4. Allow GitHub Actions to publish repository-linked packages. The workflow uses
   its built-in `GITHUB_TOKEN` with `packages: write`; no registry secret is needed.
   After the first image is published, change the `semaphoreui-mcp` GHCR package
   visibility to **Public** in its package settings and verify an anonymous pull.
   GitHub initially creates container packages as private, even for a public
   repository. See [GitHub's container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
5. Keep GitHub immutable releases disabled for this workflow: it adds assets after
   a release is published. Protect `main` and release tags against force updates;
   publish fixes as new versions rather than moving existing tags.

PyPI credentials are supplied by GitHub OIDC only in the publishing job. Do not
create or add a long-lived PyPI API token. The build and compatibility checks run
in separate jobs with read-only repository permissions.

## Prepare a release

1. Update `version` in `pyproject.toml` and `__version__` in
   `src/semaphoreui_mcp/__init__.py` to the same value. Run `uv lock` to update the
   project's entry in the lockfile. Use `X.Y.Z` for stable releases or a canonical
   Python prerelease such as `X.Y.Za1`, `X.Y.Zb1` or `X.Y.Zrc1`.
2. Move the relevant `CHANGELOG.md` Unreleased entries into a version section with
   its release date. Describe user-facing changes and any migration steps. A
   change to default tool exposure, existing tool names or argument contracts
   needs an explicit compatibility note.
3. Submit and merge the release changes into `main` after CI passes. Tags must
   point at commits reachable from `main`.
4. Create and push an annotated tag matching both version fields. For example,
   for version `0.1.0`, use `v0.1.0`. Create a GitHub release from that existing
   tag, review its release notes, then publish it. Mark versions with `a`, `b` or
   `rc` suffixes as prereleases in GitHub too.
5. Watch the **Release** workflow. It verifies the tag, both package version
   declarations, GitHub release metadata and main ancestry, then runs the full
   CI test, build and Semaphore compatibility matrix against the tagged commit.
   Publication only starts after those checks pass.
6. Verify the release assets, image platforms and installation paths. For an
   example `0.1.0` release, once both registries are public:

   ```sh
   gh release download v0.1.0 --repo johsem/semaphoreui-mcp --dir release-check
   (cd release-check && shasum -a 256 --check SHA256SUMS)
   uvx --from semaphoreui-mcp==0.1.0 semaphoreui-mcp --version
   docker buildx imagetools inspect ghcr.io/johsem/semaphoreui-mcp:0.1.0
   docker run --rm ghcr.io/johsem/semaphoreui-mcp:0.1.0 --version
   ```

Container tags use the package version without the `v` prefix. There is no
`latest` tag: retrying an older release cannot change another release's alias.
The build records the source revision, generates provenance and an SBOM, and
publishes both supported architectures. Pin the image digest when deployments
must use identical bytes.

## Recover a partial release

GitHub assets, GHCR and PyPI are separate destinations and cannot be published in
one atomic transaction. The workflow summary reports each result. A GitHub release
can be visible before its files or registry packages are ready; avoid announcing
installation commands until the required destinations have succeeded.

Use **Re-run failed jobs** for a failed release run. Existing wheel and source
distribution assets are retained; their checksums must match the release's
`SHA256SUMS`. PyPI downloads those canonical release files and skips files already
uploaded, so a partial upload can finish without rebuilding or replacing them.
GHCR failure does not prevent the independent PyPI job from running.

If PyPI was deliberately disabled, enable it after account setup and use
**Actions → Release → Run workflow**, select `main`, and enter the existing
published tag. The CLI equivalent is:

```sh
gh workflow run release.yml --ref main -f tag=v0.1.0 --repo johsem/semaphoreui-mcp
```

A full manual retry runs CI again and rebuilds the same container version, which
may change its digest when base images or build tooling have changed. To retry
only failed publication jobs, prefer the original run while its CI artifacts are
available. Never delete PyPI files to replace a release: PyPI does not allow a
filename to be reused. If published code needs fixing, release a new version.

## Routine maintenance

Review dependency and GitHub Action updates with the full CI matrix. Update the
Semaphore compatibility matrix when an upstream stable release becomes available,
retaining an older supported example and testing an available prerelease where
practical. Record what was actually tested; an upstream API change may require a
catalogue update before its newly added operations can be exposed. Follow the
[catalogue maintenance guide](catalogue-maintenance.md) for that process.
