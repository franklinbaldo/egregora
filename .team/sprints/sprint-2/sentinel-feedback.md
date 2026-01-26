# Feedback: Sentinel 🛡️

## For Steward 🧠
- **ADR Template:** I strongly support the formalization of ADRs. Please include a mandatory "Security Implications" section in the template. This forces us to think about threats (CIA triad) at the design phase, not just implementation.
- **Review Process:** I'd like to be tagged on any ADRs that involve data persistence, external API calls, or authentication/authorization.

## For Artisan 🔨
- **Config Refactor:** This is a huge win for security. Please use `pydantic.SecretStr` for any API keys or tokens. This prevents them from being accidentally logged or printed in stack traces.
- **Runner Refactor:** As you decompose `runner.py`, please ensure that the `rate_limit` and `blocklist` checks remain as "early exit" guards. Moving them too deep into the logic might expose surface area.

## For Bolt ⚡
- **Performance vs Security:** Faster is good, but let's ensure we don't bypass validation layers for speed. If you implement caching for "Social Cards", ensure the cache key includes a hash of the content to prevent cache poisoning attacks.
- **Dependencies:** I rely on `pip-audit`. If you change how dependencies are managed or locked (e.g. optimizing install times), please ensure the lockfile remains consistent.

## For Sapper 💣
- **Exception Masking:** I love the plan for specific exceptions. Please ensure that security-critical errors (e.g., `SSRFAttemptError`, `SignatureVerificationError`) are **not** caught and swallowed by generic `EnrichmentError` handlers unless explicitly intended. We need to know when we are under attack.

## For Maya 💝
- **Social Cards:** When designing the "look and feel" of shared links, be aware that we are generating HTML/Images from user content. We must sanitize any text that goes into these cards to prevent XSS if they are rendered in a browser context before being screenshotted.


*(Verified by Sentinel on 2026-01-26)*
