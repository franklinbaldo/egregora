---
title: "🛡️ Refactored Avatar Security"
date: 2026-01-16
author: "Sentinel"
emoji: "🛡️"
type: journal
---

## 🛡️ 2026-01-16 - Refactored Avatar Security

**Observation:** The `download_avatar_from_url` function in `src/egregora/agents/avatar.py` was overly complex, mixing HTTP client setup, download logic, error handling, and security validation (SSRF/TOCTOU protection) in a single block. This made the code hard to read and potentially fragile to changes, as modifying the download logic could inadvertently break the security hooks.

**Action:** I refactored the function by extracting the security and download logic into dedicated helper functions:
*   `_create_safe_client`: Encapsulates the creation of the `httpx.Client` with the critical `request` event hook for TOCTOU protection.
*   `_validate_request_hook`: The standalone validation hook.
*   `_handle_download_error`: Centralizes the error handling logic, ensuring that specific SSRF validation errors are preserved and not masked by generic error messages.
*   `_fetch_avatar_content`: Handles the download process using the safe client.

This decomposition isolates the security-critical components, making them reusable and easier to test, while simplifying the main orchestration function. Existing security tests (`tests/security/test_avatar_security.py`) passed, confirming no regressions.

**Reflection:** Encapsulating security controls (like client configuration and error handling) in factory functions or dedicated helpers is a strong pattern. It prevents "security drift" where future refactors might accidentally remove inline security checks. This approach should be applied to other network-facing components if encountered.
