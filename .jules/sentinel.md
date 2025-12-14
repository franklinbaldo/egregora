## 2025-05-18 - [HIGH] Stored XSS via WhatsApp Exports
**Vulnerability:** WhatsApp chat exports containing HTML/JS tags (e.g., `<script>`) were processed as plain text and rendered as raw HTML in the MkDocs output (due to `md_in_html` extension and default Markdown behavior), leading to Stored XSS.
**Learning:** Even when the primary input is text-based (chat logs), downstream components (Markdown renderers, LLMs) may interpret special characters as code or formatting. Trusting input fidelity can compromise output security.
**Prevention:** Sanitized input at the ingestion layer (`_normalize_text`) by HTML-escaping special characters. This ensures the data is stored safely and rendered as text, preventing execution while preserving the original visual content for the user.
