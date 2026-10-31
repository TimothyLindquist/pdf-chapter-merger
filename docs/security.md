# Security design and remaining risks

This describes application controls, not an independent security certification.

## Processing and output controls

- Only pypdf parses and writes document content. ReportLab, Pillow, charset-normalizer, and setuptools are not part of the application install set.
- The GUI does not parse PDFs. A gated worker receives input only after Windows job assignment succeeds. Failure to establish limits prevents processing.
- The Windows job allows one process with 768 MiB committed memory and terminates its worker when the job closes. The parent enforces a two-minute timeout and supports cancellation.
- Limits also cover input count and aggregate bytes, pages, output bytes, object visits, annotations per page, and bookmark nesting.
- Source annotation objects are not imported. Scripts, active-action keys, attachments, forms, and multimedia references are removed from cloned dictionaries. Simple links are reconstructed from allowed fields and schemes; action chains are discarded.
- Every encrypted input is rejected, including documents that accept an empty password. No silent decryption or encryption-preservation promise is made. Output is unencrypted.
- Selected source paths and aliases cannot be the destination. Existing output is replaced only after successful processing.
- During parsing, output is staged as a Windows delete-pending file. New readers cannot open it by path. Windows removes it when handles close, including after cancellation or abrupt process exit. Successful publication clears deletion status immediately before atomic replacement.

## Important boundaries

Windows jobs enforce resources and process creation; they do not provide a complete filesystem or network sandbox. Unknown parser defects or malicious page content can still pose risks, especially when the result is opened in a PDF viewer. Keep the operating system, Python interpreter, and viewer maintained.

Form values, comments, annotations, signatures, and advanced PDF features can be lost or changed. Review output before sharing it. This app is not suitable for workflows requiring preservation of signatures or interactive forms.

Output inherits destination-folder permissions. OneDrive and other services can copy files independently; the app does not control those services. Deletion is not secure erasure. A power loss or abrupt termination during the brief final-publication window can leave an intermediate file. Do not run as administrator or treat the app as protection against another user who can modify its source, lock files, or dependency directory.

## Supply chain

Package versions, URLs, and SHA-256 hashes are committed. Wheel downloads are explicit and restricted to the official HTTPS package-file host. Normal installation is offline, hash-checked, wheels-only, and does not execute source build hooks. A compromised account or repository could still change code and expected hashes together.

CI queries OSV for exact locked package versions and fails on returned advisories or lookup errors. This is a known-vulnerability check, not exhaustive dependency source review. CI actions are pinned to full commit IDs and run with read-only repository permissions; no publishing credentials are used in pull-request workflows.

## Verification

The regression suite checks chapter ordering, source bookmark destinations, source-file integrity, malformed/encrypted input handling, active-action removal and allowed-link preservation, output protection, cancellation/timeout cleanup, OS memory and child-process limits, delete-pending read denial, abrupt-exit cleanup, and installer tamper rejection. It uses synthetic documents and inert JavaScript markers, without opening hostile PDFs in a viewer.
