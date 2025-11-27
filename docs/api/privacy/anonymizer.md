# Privacy Anonymizer

The anonymizer stage removes or masks personally identifiable information before data leaves the ingestion boundary.

## Key Tasks
- Apply deterministic UUID mapping to authors and threads.
- Strip or redact sensitive fields that cannot be safely stored.
- Emit PII audit signals for downstream observability.

Additional implementation details will be documented as the privacy module matures.
