# Security policy

## Reporting a vulnerability

After this repository is hosted on GitHub, use **Security > Report a vulnerability** if private vulnerability reporting is enabled. If unavailable, request a private reporting channel from the maintainer without posting exploit details or confidential PDFs in a public issue. Do not attach personal documents to public issues.

Maintainers should enable private vulnerability reporting before inviting public use. No monitored contact address or guaranteed response time is claimed by this template.

## Supported version

Security fixes target the latest release and the default branch. Older versions are not maintained separately. Before the first release, the project should be treated as pre-release software.

## Scope and limits

The app processes documents locally, but is not a complete security sandbox or a validated PDF sanitizer. Output is unencrypted. Other software may sync files independently. See [the security design](docs/security.md) for controls, tradeoffs, tests, and remaining risks.

Do not interpret a passing dependency scan as evidence that no vulnerabilities exist. Keep Python, Windows, and your PDF viewer patched. The original local audit archives are intentionally not published; they are not an independent security certification.
