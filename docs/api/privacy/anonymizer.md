# Privacy - Anonymizer

Anonymize author names in conversation DataFrames using deterministic UUIDs.

## Overview

The anonymizer ensures that real names never reach the LLM by replacing them with deterministic UUIDs before any AI processing.

## API Reference

::: egregora.privacy.anonymizer
    options:
      show_root_heading: true
      show_source: true
      members_order: source

## Usage

### Basic Anonymization

```python
from egregora.privacy import anonymize_dataframe

# Parse and anonymize
df = parse_whatsapp_export("export.zip")
df_anon = anonymize_dataframe(df)

# Before:
# author: "Alice"
# message: "Hey Bob, how are you?"

# After:
# author: "a3f2b91c"
# message: "Hey b7e4d23a, how are you?"
```

### Preserve Mapping

```python
from egregora.privacy import anonymize_dataframe, save_mapping

df_anon, mapping = anonymize_dataframe(df, return_mapping=True)

# Save mapping for later (local only!)
save_mapping(mapping, ".egregora/mapping.json")

# Mapping format:
# {
#   "Alice": "a3f2b91c",
#   "Bob": "b7e4d23a"
# }
```

### Reverse Anonymization

```python
from egregora.privacy import reverse_anonymization, load_mapping

# Load saved mapping
mapping = load_mapping(".egregora/mapping.json")

# Reverse UUIDs back to names (for local display)
df_original = reverse_anonymization(df_anon, mapping)
```

## Implementation Details

### UUID Generation

UUIDs are generated using SHA-256:

```python
import hashlib

def generate_uuid(name: str, salt: str = "") -> str:
    """Generate deterministic UUID from name."""
    content = f"{name}{salt}".encode('utf-8')
    hash_digest = hashlib.sha256(content).hexdigest()
    return hash_digest[:8]  # First 8 characters
```

**Properties**:

- **Deterministic**: Same name → same UUID
- **Collision-resistant**: Different names → different UUIDs
- **One-way**: UUID → name requires the mapping
- **Short**: 8 characters for readability

### Anonymization Scope

The anonymizer replaces names in:

- **Author field**: Primary identifier
- **Message content**: "@mentions" and direct references
- **Quoted replies**: Referenced authors

**Not anonymized**:

- Timestamps
- Media references
- Non-name content

### Performance

- **O(n) time**: Single pass over DataFrame
- **Lazy evaluation**: Uses Ibis for efficiency
- **Regex matching**: Fast pattern replacement

## Advanced Usage

### Custom Salt

Add randomness to UUIDs:

```python
df_anon = anonymize_dataframe(
    df,
    salt="my-secret-salt"
)

# Same name, different salt → different UUID
```

**Use case**: Multiple independent blogs from same group.

### Selective Anonymization

Anonymize only specific authors:

```python
from egregora.privacy import anonymize_authors

df_anon = anonymize_authors(
    df,
    authors=["Alice", "Bob"],  # Only anonymize these
    keep_others=True           # Keep other names as-is
)
```

### Alias Support

Use display names instead of UUIDs:

```python
from egregora.privacy import apply_aliases

aliases = {
    "a3f2b91c": "Casey",
    "b7e4d23a": "Jordan"
}

df_display = apply_aliases(df_anon, aliases)
```

## Security Considerations

### What's Protected

- ✅ Real names never sent to LLM
- ✅ Deterministic mapping for consistency
- ✅ Reversible for local use

### What's Not Protected

- ❌ Message content (still sent to LLM)
- ❌ Context clues (e.g., "my name is Alice")
- ❌ Metadata (timestamps, media types)

### Best Practices

1. **Never commit mappings**: Add to `.gitignore`
2. **Secure storage**: Encrypt mapping files if needed
3. **Review content**: Check for name mentions in messages
4. **Use aliases**: For public display

## Examples

### Complete Privacy Pipeline

```python
from egregora.ingestion import parse_whatsapp_export
from egregora.privacy import anonymize_dataframe, detect_pii

# Parse
df = parse_whatsapp_export("export.zip")

# Anonymize
df_anon, mapping = anonymize_dataframe(df, return_mapping=True)

# Check for PII
pii_results = detect_pii(df_anon)

# Save mapping locally
save_mapping(mapping, ".egregora/mapping.json")

# Now safe to process with LLMs
```

### Public Blog with Aliases

```python
# Anonymize for LLM
df_anon = anonymize_dataframe(df)

# Generate posts (uses UUIDs)
posts = generate_posts(df_anon, client, rag_store)

# Apply aliases for public display
aliases = load_aliases(".egregora/aliases.json")
posts_display = apply_aliases_to_posts(posts, aliases)

# Publish with friendly names
write_posts(posts_display, "docs/posts/")
```

## See Also

- [Privacy - PII Detector](detector.md) - Scan for sensitive information
- [User Guide - Privacy Model](../../guide/privacy.md) - Conceptual overview
- [Core - Models](../core/models.md) - Data structures
