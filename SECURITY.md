# Security Policy

## Supported Versions

| Branch/Tag | Status                  |
|------------|-------------------------|
| `main`     | :white_check_mark: Active (latest development) |
| `dev`      | :white_check_mark: Active (staging) |
| Others     | :x: No longer supported |

Security updates for active branches only.

## Reporting a Vulnerability

Report vulnerabilities responsibly:

1. **Preferred**: [GitHub Security Advisories](https://github.com/franklinbaldo/egregora/security/advisories/new) (private until patch).
2. **Alternative**: Open a private GitHub Issue labeled "security" or email `security@egregora.example` (TBD).
3. **Critical**: Direct maintainer contact via GitHub profile.

Expect:
- Acknowledgment within 48 hours.
- Patch/targeted fix within 7-14 days (priority).
- Disclosure coordination (CVSS 7+ coordinated).

## Secure Development Practices

- Pre-commit hooks (run `python dev_tools/setup_hooks.py`) enforce linting, secrets scanning, formatting on every commit.
- Dependencies pinned via `uv.lock`; audit with `uv run ruff check --select=security src/`.
- No committed secrets; env vars only (e.g., `GOOGLE_API_KEY`).
- Privacy-by-design: anonymization before LLM; PII detection in pipeline.

## Scope

In-scope: core pipeline (src/egregora), CLI, adapters.
Out-of-scope: 3rd-party (Gemini API, DuckDB vulns reported upstream).

Thanks for helping keep Egregora secure!
