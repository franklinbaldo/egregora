# Privacy - PII Detector

Detect personally identifiable information (PII) in conversation text.

## Overview

The PII detector scans messages for sensitive information like phone numbers, emails, addresses, and more.

## API Reference

::: egregora.privacy.detector
    options:
      show_root_heading: true
      show_source: true
      members_order: source

## Usage

### Basic Detection

```python
from egregora.privacy import detect_pii

df = parse_whatsapp_export("export.zip")
pii_results = detect_pii(df)

# Returns DataFrame with columns:
# - message_id: Original message ID
# - pii_type: Type of PII detected
# - pii_value: Detected value
# - confidence: Detection confidence (0-1)
```

### PII Types

| Type | Examples | Pattern |
|------|----------|---------|
| `phone` | `+1-555-123-4567`, `(555) 123-4567` | International, US formats |
| `email` | `user@example.com` | Standard email format |
| `address` | `123 Main St, City, ST 12345` | Street addresses |
| `ssn` | `123-45-6789` | US Social Security |
| `credit_card` | `4111-1111-1111-1111` | Major card types |
| `ip_address` | `192.168.1.1` | IPv4, IPv6 |
| `url` | `https://example.com` | Web URLs |

### Redaction

```python
from egregora.privacy import detect_pii, redact_pii

# Detect PII
pii_results = detect_pii(df)

# Redact detected PII
df_redacted = redact_pii(df, pii_results)

# Before: "Call me at 555-123-4567"
# After:  "Call me at [REDACTED]"
```

## Configuration

### Sensitivity Levels

```python
from egregora.privacy import detect_pii, DetectionLevel

# Low: Only high-confidence matches
pii_results = detect_pii(df, level=DetectionLevel.LOW)

# Medium: Balanced (default)
pii_results = detect_pii(df, level=DetectionLevel.MEDIUM)

# High: Include potential matches
pii_results = detect_pii(df, level=DetectionLevel.HIGH)
```

### Custom Patterns

```python
from egregora.privacy import detect_pii, add_pattern

# Add custom PII pattern
add_pattern(
    name="employee_id",
    pattern=r"EMP-\d{6}",
    description="Company employee ID"
)

pii_results = detect_pii(df, include_custom=True)
```

## Examples

### Audit PII Exposure

```python
from egregora.privacy import detect_pii

df = parse_whatsapp_export("export.zip")
pii_results = detect_pii(df)

# Count PII by type
pii_summary = (
    pii_results
    .group_by("pii_type")
    .aggregate(count=pii_results.count())
)

print(pii_summary.execute())
# pii_type    | count
# ------------|------
# phone       | 15
# email       | 8
# address     | 3
```

### Filter Messages with PII

```python
# Get message IDs with PII
pii_message_ids = pii_results.message_id.unique()

# Filter out messages with PII
df_clean = df.filter(~df.message_id.isin(pii_message_ids))

# Or redact instead of filter
df_redacted = redact_pii(df, pii_results)
```

## See Also

- [Privacy - Anonymizer](anonymizer.md) - Name anonymization
- [User Guide - Privacy](../../guide/privacy.md) - Privacy overview
