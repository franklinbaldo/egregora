# 🛡️ Privacy & Security

> **Principle:** Privacy-First by Design.
> **Guardian:** [Curator (Target)](Team-Roster.md)

Egregora is built on a "Privacy-First" foundation. We do not track users, we do not leak metadata, and we minimize external dependencies.

## 🚫 The "No External Requests" Mandate

To prevent IP leakage and tracking by third parties, the generated site and the application itself must **NOT** make requests to external domains by default.

### 1. Localize Assets
- **Fonts:** Google Fonts must be stripped or self-hosted. We do not use `@import url('https://fonts.googleapis.com/...')`.
- **Scripts:** Libraries like MathJax or Analytics scripts from CDNs (e.g., `unpkg.com`, `cdnjs.com`) are prohibited.
- **Images:** All UI assets must be bundled locally.

### 2. Implementation Strategy
- **MkDocs Configuration:** Use `privacy` plugins or explicit configuration to disable external fetchers.
- **CSS:** Bundle required fonts in `assets/fonts/` and use `@font-face`.

## 🧹 PII Stripping (Future)

The ETL pipeline is responsible for identifying and redacting Personally Identifiable Information (PII) before it reaches the model context window, ensuring that even the LLM provider does not receive sensitive user data unless explicitly authorized.

## 🔒 Security Protocols

See [Protocols & Workflows](Protocols.md) for details on:
- API Key Management
- Secret Rotation
- Audit Logs
