# Architecture

```text
.github/                 CI, dependency updates, issue and PR templates
docs/                    Architecture, security design, publishing guide
scripts/                 Bootstrap, launch, test, dependency and release tools
src/pdf_chapter_merger/   Application package
tests/                   Synthetic PDF and Windows integration tests
install-manifest.json    Exact package URLs, versions, filenames, hashes
requirements.txt         Matching pip hash lock
pyproject.toml           Package metadata and optional build backend
```

`app.py` manages Tkinter and polls a `MergeTask`; it does not import pypdf. `processing.py` opens a delete-pending staged output and creates a worker. `windows_limits.py` assigns the worker to a Windows job before parsing is released through its input gate. The job caps memory and process count and kills the worker when its parent closes the job.

`worker.py` starts with isolated Python flags and site initialization disabled. After the gate it adds only the application package directory and its private dependency directory. `merge.py` builds the PDF, strips active structures from cloned objects, and reconstructs allowed links. The parent publishes successful output by atomic replacement and handles cancellation, timeout, and cleanup.

The source launcher runs `scripts/bootstrap.py` first. Wheels are verified before use, and an updated pip wheel bootstraps installations instead of relying on an old installed pip. Package downloads are a separate explicit command. The GUI and worker skip ambient Python paths, user site packages, and `.pth` startup hooks.

Version metadata lives in `pyproject.toml` and `src/pdf_chapter_merger/__init__.py`; update both for a release. Runtime package updates must keep `requirements.txt`, `install-manifest.json`, and the pypdf metadata pin consistent.
