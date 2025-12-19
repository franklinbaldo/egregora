## 2025-12-18 - [CRITICAL] Supply Chain Risk in Jules Scheduler
**Vulnerability:** The `jules_scheduler.yml` workflow executed code from an external repository (`franklinbaldo/jules_scheduler`), introducing a supply chain risk and opaque behavior.
**Learning:** Relying on external, unverified wrappers for simple API interactions adds unnecessary attack surface and complexity. "Wrap logic" often hides what is actually happening.
**Prevention:** Removed the external dependency entirely and replaced it with a transparent, local Python script (`scripts/jules_scheduler.py`) that interacts directly with the Jules API. This follows the principle of "Verify Everything" by owning the execution logic.
