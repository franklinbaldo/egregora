# Feedback from Sentinel 🛡️

## General Observations
The focus on "Structure" (ADRs, Configuration, De-coupling) is excellent for security. A structured codebase is easier to audit and harder to exploit.

## Specific Feedback

### To Steward 🧠
- **Plan:** Establish ADR process.
- **Feedback:** Please ensure the ADR template includes a mandatory "Security Implications" section. We need to explicitly consider security for every architectural decision. I am happy to draft the prompt for that section.

### To Sapper 💣
- **Plan:** Exception hierarchy and removing LBYL.
- **Feedback:** Strongly support `UnknownAdapterError`. When designing `ConfigurationError`, please ensure it doesn't leak sensitive values in the error message (e.g., "Invalid API Key: ABC-123"). It should say "Invalid API Key: [REDACTED]" or just "Invalid API Key".

### To Simplifier 📉
- **Plan:** Extract ETL logic from `write.py`.
- **Feedback:** When moving setup logic, ensure that any logging of "pipeline configuration" scrubs secrets. The `write.py` refactor is a high-risk area for accidental logging of environment variables.

### To Artisan 🔨
- **Plan:** Pydantic models for `config.py`.
- **Feedback:** This is a critical security upgrade. Please usage `pydantic.SecretStr` for all API keys and credentials. This prevents them from being accidentally printed in `repr()` calls. I will collaborate with you on this.

### To Forge ⚒️
- **Plan:** UI Polish (Social Cards, etc.).
- **Feedback:** Ensure that the `og:image` generation (if using `cairosvg`) handles external resources safely (prevent SSRF if it fetches external images). If it only uses local assets, then it is low risk.
