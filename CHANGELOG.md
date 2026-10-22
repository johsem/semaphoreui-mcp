# Changelog

User-facing changes are recorded here. Versions follow `MAJOR.MINOR.PATCH`;
prerelease versions use Python's `a`, `b` or `rc` suffixes. Before version 1.0,
minor releases may change interfaces; release notes will identify migration steps.

## Unreleased

### Added

- An opt-in core tool profile for common project and task workflows, while
  retaining the complete catalogue as the default.
- Contributor guidance, issue and pull request templates, private security
  reporting instructions, and a documented catalogue maintenance process.
- Automated dependency updates and broader Python compatibility checks.
- A release workflow with validated version tags, GitHub distribution assets and
  checksums, multi-platform GHCR containers, and optional PyPI Trusted Publishing.

### Changed

- Clarified that the bundled Semaphore schema source version is provenance, not a
  runtime version restriction; removed fixed tool counts from user-facing copy.
- Added live compatibility checks against older, catalogue-source and prerelease
  Semaphore versions.

The repository currently declares version `0.1.0`. These entries describe work
awaiting a tagged release; they do not imply that packages have been published.
