# Privacy Anonymizer

The anonymizer module provides utility functions for removing or masking personally identifiable information (PII).

## Usage

This module is primarily used by Input Adapters to anonymize data *before* it enters the main processing pipeline. It is not a standalone pipeline stage.

## Key Tasks
- Apply deterministic UUID mapping to authors and threads.
- Strip or redact sensitive fields that cannot be safely stored.
- Emit PII audit signals for downstream observability.

## Integration
Input adapters (like `WhatsAppAdapter`) invoke `anonymize_table` to ensure that the intermediate representation (IR) contains only anonymized data.

```python
from egregora.privacy.anonymizer import anonymize_table

# Inside an adapter
messages_table = parse_source(...)
anonymized_table = anonymize_table(messages_table, enabled=True)
```
