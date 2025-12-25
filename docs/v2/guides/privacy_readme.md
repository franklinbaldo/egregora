# Privacy

The `egregora.privacy` module has been removed. Privacy and anonymization logic (PII scrubbing, author anonymization) is now handled directly by input adapters (e.g., `egregora.input_adapters.whatsapp.parsing`) or relevant transformations.

This ensures privacy logic is integrated where data ingestion happens, rather than being an isolated concern.
