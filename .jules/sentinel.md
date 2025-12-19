## 2025-12-18 - [CRITICAL] Supply Chain Risk in Jules Scheduler
**Vulnerability:** The `jules_scheduler.yml` workflow executed code from an external repository (`franklinbaldo/jules_scheduler`) using `@main`, allowing potential supply chain attacks if the external repository were compromised.
**Learning:** Using `@main` or `@latest` for external dependencies in CI/CD pipelines creates a window of vulnerability where malicious changes are immediately propagated to your environment.
**Prevention:** Pinned the `uvx` execution to a specific commit SHA (`4566f12...`) to ensure only verified code is executed. Future updates will require manual verification and SHA updates.
