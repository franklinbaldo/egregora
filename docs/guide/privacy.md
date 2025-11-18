# Privacy & Anonymization

Egregora's privacy-first design ensures your personal information remains under your control.

## Privacy-First Philosophy

Egregora operates on the principle that your personal data should never leave your machine unless you explicitly allow it. All privacy-sensitive processing happens locally, on your computer, before any information is sent to external services for enrichment.

## How Privacy Protection Works

### 1. PII Detection

When your data enters the pipeline, Egregora first detects potentially sensitive information:

- **Names**: People's names and nicknames
- **Contact Info**: Email addresses, phone numbers
- **Locations**: Specific places and addresses
- **Other PII**: Dates of birth, ID numbers, etc.

Detection happens through a combination of:
- Pre-trained NLP models for entity recognition
- Regular expressions for common patterns
- Contextual analysis to reduce false positives

### 2. Anonymization

Once detected, PII is replaced with anonymous tokens:

```
Original: "Hey John, let's meet at the Central Park tomorrow at 3pm."
Anonymized: "Hey ANON_PERSON_1, let's meet at ANON_LOCATION_1 tomorrow at 3pm."
```

The anonymization maintains referential integrity, so if "John" appears 50 times in your data, it will always be replaced with the same token (`ANON_PERSON_1`).

### 3. Privacy Gate

A privacy gate system controls what information flows between pipeline stages:
- Only anonymized data passes to AI enrichment services
- Original PII remains isolated in a secure context
- Configurable privacy levels for different use cases

## Configuration Options

### Privacy Settings

You can configure privacy processing in your `config.yaml`:

```yaml
privacy:
  enabled: true                 # Enable PII detection and anonymization
  anon_threads: 4              # Number of threads for anonymization
  detect_pii: true             # Whether to detect PII
  anonymize_pii: true          # Whether to anonymize detected PII
  pii_types:                   # Types of PII to detect
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - PERSON
    - LOCATION
  anon_prefix: "ANON_"         # Prefix for anonymized entities
```

### Granular Controls

You can customize which types of PII are detected:

- `EMAIL_ADDRESS`: Email addresses
- `PHONE_NUMBER`: Phone numbers
- `PERSON`: Names of people
- `LOCATION`: Place names and addresses
- `ORGANIZATION`: Company and organization names
- `DATE`: Specific dates
- `MONEY`: Financial information

## Data Flow with Privacy

Here's how your data flows through the privacy layer:

```
Input Data → PII Detection → Anonymization → Enrichment → Output
              ↓              ↓
         Store Original    Use Anonymized
         (Isolated)       for AI Services
```

Only the anonymized version is sent to external AI services for enrichment, ensuring no PII is exposed to third parties.

## Anonymization Tokens

Egregora creates consistent tokens for the same entities:

- `ANON_PERSON_1`: First unique person detected
- `ANON_PERSON_2`: Second unique person detected
- `ANON_LOCATION_1`: First unique location
- `ANON_EMAIL_1`: First unique email address

This preserves context relationships while protecting privacy. When "John" talks to "Mary", the anonymized data maintains that ANON_PERSON_1 talked to ANON_PERSON_2.

## Verification

You can verify privacy protection by:

1. Checking that output contains anonymized tokens instead of PII
2. Confirming that external AI services only received anonymized data
3. Using the privacy report feature (if enabled) to see what PII was detected

## Limitations & Considerations

- Context-based de-anonymization is still theoretically possible in rich conversational data
- Additional metadata in attachments (EXIF data in images, etc.) should be handled separately
- The privacy layer is as effective as the PII detection accuracy
- Review anonymized output to ensure privacy requirements are met

## Best Practices

- Always enable privacy features by default
- Regularly review anonymized output for privacy leaks
- Use conservative PII detection settings when in doubt
- Consider additional privacy measures for highly sensitive data