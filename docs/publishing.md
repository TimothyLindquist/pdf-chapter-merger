# Publishing on GitHub

The repository is prepared locally. No remote repository, public release, or GitHub settings are created by these files.

## Create the remote

1. Create an empty GitHub repository named `pdf-chapter-merger` under your account or organization. Choose visibility deliberately. Do not generate a second README or license.
2. In this local repository, review `git status` and the tracked file list. There should be no PDFs, wheels, environments, audit archives, or personal files.
3. Add the remote URL copied from GitHub and push the local `main` branch. A first commit may need your Git name/email configured locally; use your GitHub no-reply address if you want email privacy.

```powershell
git add .
git commit -m "Prepare initial public source release"
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Replace the URL placeholder with the actual repository URL. If an initial commit already exists, skip the first two commands.

## Configure the hosted repository

- Enable private vulnerability reporting before public use.
- Enable dependency graph, vulnerability alerts, and secret scanning/push protection where available for the repository/account.
- Require pull requests and the Windows CI job on `main`. Enable review requirements suited to the number of maintainers; a one-maintainer project should avoid a rule that makes changes impossible.
- Keep workflow permissions read-only by default. Do not introduce `pull_request_target` to execute pull-request code.
- Review Dependabot's pinned-action updates; dependency package pins also need the manifest update process in `CONTRIBUTING.md`.
- Add the repository description and topics such as `pdf`, `windows`, `python`, and `tkinter`.

## Build an offline release

From a reviewed clean revision on Windows:

```powershell
python -I scripts/fetch_wheels.py --check-advisories
python -I scripts/bootstrap.py
python -I -S scripts/run_tests.py
python -I scripts/build_release.py
python -I scripts/smoke_release.py
```

The build creates an offline source ZIP and a matching `.sha256` file under ignored `dist/`. An explicit allowlist excludes `.git`, environments, personal files, audit archives, and build caches. The bundle includes application source, tests, maintenance tools, documentation, and official dependency wheels with their license files. Python itself is not included. The smoke check extracts the bundle into a temporary location, installs offline, initializes the GUI, and merges synthetic pages through the bounded worker.

Test the extracted bundle in a fresh location, including GUI launch, a multi-file merge, cancellation, and bookmarks. Review the release notes and known limitations. Then create a GitHub release for a reviewed version tag and attach the ZIP and checksum. The included CI produces candidate artifacts for manual review; it does not publish releases or push tags.

GitHub's automatically generated source ZIP lacks ignored dependency wheels. Its README therefore instructs users to run the explicit verified download step. The offline release ZIP is the convenient download for end users.
