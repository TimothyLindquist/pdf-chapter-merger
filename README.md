# PDF Chapter Merger

A local Windows app that combines PDFs into one document, with chapters named after the source filenames.

- Add PDFs and arrange their order.
- Add optional chapter title pages.
- Navigate the result using chapter bookmarks and retained source bookmarks.
- Process documents locally with bounded memory use, a timeout, and cancellation.

**Requirements:** Windows 10/11, 64-bit CPython 3.11 with Tkinter, and a PDF viewer. Use a maintained Python 3.11 patch release. macOS and Linux are not supported.

## Start

From an offline release bundle: extract the complete archive, then double-click **Start PDF Merger.bat**. Python must be available as `python` on PATH. The first launch creates a private `.venv` and installs only the included, hash-verified wheels. Subsequent launches need no internet.

From a Git clone or GitHub's **Download ZIP**, prepare the downloaded packages once from PowerShell in the repository folder:

```powershell
python -I scripts/fetch_wheels.py
```

This downloads only the exact wheels listed in the committed manifest from the official Python package host and verifies their SHA-256 hashes. It does not install packages or execute build scripts. Then double-click the launcher. Downloaded packages are deliberately excluded from Git history.

## Merge documents

1. Choose **Add PDFs** and select your documents.
2. Use **Move up**, **Move down**, and **Remove** to arrange chapters.
3. Choose whether to insert chapter title pages.
4. Choose **Merge and save PDF**, then **Open result**.

Bookmark names use the full filename without `.pdf`. Open your PDF viewer's bookmarks sidebar to navigate chapters. Title pages support Western European characters, including Swedish letters; other characters may display as `?`, while the full Unicode bookmark name remains available.

## Important document behavior

**Encrypted files are rejected, and output is unencrypted.** Export an unencrypted source copy deliberately before merging an encrypted document.

Scripts, launch actions, embedded attachments, multimedia, forms, comments, and other annotations are removed. **Form values and comments may disappear.** Ordinary HTTP/HTTPS links, plain email links, and internal page links are rebuilt from an allowlist. Review the result before sharing it. Existing digital signatures do not remain valid after merging.

The app does not upload documents. OneDrive, backup tools, or other software can independently copy files saved into synced folders. For sensitive documents, choose an appropriate unsynced destination and access permissions.

Limits: 100 input files, 256 MiB combined input, 2,000 output pages, 256 MiB output, 768 MiB worker memory, and two minutes per merge. The worker cannot start child processes. These controls reduce risk but are **not a complete security sandbox or a guarantee that hostile PDFs are harmless**. See [security design and limitations](docs/security.md).

## Development and publishing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and tests, [architecture](docs/architecture.md) for the source layout, and [publishing](docs/publishing.md) for GitHub settings and offline release packaging.

The application is MIT-licensed. Third-party packages retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
