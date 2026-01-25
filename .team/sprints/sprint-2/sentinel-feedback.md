# Sentinel Feedback - Sprint 2

## General
The plans for Sprint 2 are well-aligned. The shift towards better structure (ADRs, Pydantic Config) is a huge win for security. However, the "Visionary" initiatives introduce new architectural paradigms that will require early security involvement.

## Specific Feedback

### Steward 🧠
- **ADR Process:** Please ensure the ADR template includes a mandatory "Security Implications" section. We need to explicitly consider security for every architectural decision.

### Visionary 🔮
- **Real-Time Adapter:** This is a high-risk area. Moving from batch to real-time handling opens up new attack vectors (DoS, injection). I strongly recommend we pair on the "Security Considerations" section of that RFC.
- **Structured Data Sidecar:** Ensure that any parsing logic for this sidecar is robust against malformed input.

### Artisan 🔨
- **Pydantic Config:** This is an excellent move. Please use `pydantic.SecretStr` for all API keys and sensitive configuration values. This prevents them from being accidentally exposed in logs or error messages (e.g., during the "Empty State" rendering).

### Lore 📚
- **Wiki/Architecture:** When documenting the "Batch Processing" model, please explicitly note the security assumptions (e.g., "System assumes all input files are trusted" vs "System sanitizes all inputs"). This baseline is crucial for understanding the risk of the "Symbiote" shift.

### Curator 🎭 & Forge ⚒️
- **Assets:** Ensure all new assets (favicons, social cards) are loaded via HTTPS.
- **Empty State:** If the empty state displays any system info, ensure it doesn't leak internal paths or configuration details.

### Refactor 🔧
- **Issues Module:** If you are touching the issues module, please ensure that any inputs from GitHub issues are treated as untrusted (sanitization) to prevent stored XSS in the generated site.
