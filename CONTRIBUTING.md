# Contributing

Use Windows and 64-bit Python 3.11. The supported end-user distribution is the launcher/offline source bundle, rather than a PyPI release.

## Set up and test

From PowerShell at the repository root:

```powershell
python -I scripts/fetch_wheels.py --check-advisories
python -I scripts/bootstrap.py
python -I -S scripts/run_tests.py
```

Tests use only the standard library and the locked pypdf dependency. They create synthetic PDFs in temporary folders; do not add personal PDFs as fixtures. Windows job limits and staging behavior are integration-tested rather than mocked away.

To run the app with the supported isolated launch:

```powershell
& '.\Start PDF Merger.bat'
```

Keep PDF parsing in the worker. The GUI must not import the parser. Do not replace the gated worker with a background thread or silently fall back when Windows limits cannot be applied. Keep changes to security-sensitive code small and include regression tests for changes to active-content handling, output publication, and limits.

## Dependency updates

Only pip and pypdf are in the application's locked install set. Read upstream changes and advisories, select explicit versions, then use the maintainer helper:

```powershell
python -I scripts/update_dependencies.py --pip-version 26.2.2 --pypdf-version 6.21.4
python -I scripts/bootstrap.py
python -I -S scripts/run_tests.py
```

The example names the current pins; choose reviewed patched versions for an update. The helper queries PyPI and OSV, updates `install-manifest.json` and `requirements.txt`, and downloads verified wheels without executing them. Review both lock files together. OSV results go to ignored `build/dependency-audit.json`. If the helper is interrupted, restore or complete both lock files before running setup; disagreement fails closed.

`pyproject.toml` repeats the runtime pypdf pin for Python package metadata and separately pins the optional source-package build backend. Keep those versions consistent with a reviewed update; the normal launcher does not execute that build backend. GitHub Actions updates are proposed by Dependabot and should retain full commit-SHA pins.

## Pull requests

Explain the user-visible change, relevant security implications, and validation. Run the complete Windows suite before submission. Never include credentials, personal paths, local audit archives, downloaded wheels, `.venv`, or user documents. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
