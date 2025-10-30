# Anonymization in Egregora v2

## Overview

Egregora v2 includes **automatic, deterministic anonymization** of all personal identifiable information (PII) using UUID5-based pseudonyms.

## How It Works

### 1. Author Anonymization

All author names are replaced with 8-character UUID5 hashes:

```
João Silva → a1b2c3d4
Maria Santos → e5f6g7h8
joão silva → a1b2c3d4  (case-insensitive, same hash)
```

**Key Features:**
- ✅ Deterministic: Same author always gets the same pseudonym
- ✅ Case-insensitive: "João" and "joão" → same hash
- ✅ Compact: 8 hex characters (not full UUID)
- ✅ Collision-resistant: UUID5 namespace-based

### 2. Mention Anonymization

WhatsApp mentions use special Unicode markers (`\u2068` and `\u2069`). These are detected and replaced:

```
Original: "Hey \u2068João Silva\u2069 how are you?"
Anonymized: "Hey a1b2c3d4 how are you?"
```

### 3. Columnar Processing

Anonymization happens on **Ibis Tables** backed by DuckDB. We keep everything
lazy and only call `.execute()` when we truly need a pandas object:

```python
import ibis
from egregora.anonymizer import anonymize_table

messages = ibis.memtable([
    {"author": "João Silva", "message": "Olá"},
    {"author": "Maria Santos", "message": "Oi @João"},
])

anonymized = anonymize_table(messages)

# Conversion to pandas (still needed when rendering markdown today)
preview = anonymized.limit(5).execute()
```

## Implementation

### Pipeline Integration

Anonymization happens **before any LLM interaction**:

```
ZIP Export → Parse → Anonymize → Loader → Agents (LLM) → Post
                        ↑                      ↑
                  PII removed here      Only sees pseudonyms
```

**Critical: Real names NEVER reach the LLM**

The `parse_export()` function automatically anonymizes:

```python
import ibis

# In parser.py
table = ibis.memtable(rows).order_by("timestamp")
table = anonymize_table(table)  # ← PII removed HERE
return table

# In loader.py
table = parse_export(export)  # Already anonymized Table
messages = create_messages(table)  # Uses anonymized data lazily

# In writer/
prompt_frame = table.execute()  # pandas conversion happens here today
await llm.generate(prompt_frame.to_markdown(index=False))
```

### Code Location

- **`src/egregora/anonymizer.py`**: Core anonymization logic
- **`src/egregora/parser.py`**: Integration into parsing pipeline

## Privacy Guarantees

### What is Anonymized

- ✅ Author names (column `author`)
- ✅ WhatsApp mentions in messages (Unicode markers)
- ✅ Consistent across the entire pipeline

### What is NOT Anonymized

- ❌ Message content (beyond mentions)
- ❌ Media filenames
- ❌ URLs
- ❌ Timestamps

**Note**: Privacy validation (`privacy.py`) still scans for phone numbers in final output.

## Examples

### Input (WhatsApp Export)

```
10:00 - João Silva: Hey everyone!
10:01 - Maria Santos: Hi @João Silva, how are you?
10:02 - Pedro Costa: Good morning!
```

### After Anonymization

```
10:00 - a1b2c3d4: Hey everyone!
10:01 - e5f6g7h8: Hi a1b2c3d4, how are you?
10:02 - f9g0h1i2: Good morning!
```

### In Generated Post

```markdown
## Morning Discussion

The group started the day with greetings. a1b2c3d4 initiated
the conversation, followed by e5f6g7h8 and f9g0h1i2.
```

## Technical Details

### UUID5 Namespace

```python
NAMESPACE_AUTHOR = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
```

This ensures deterministic hashing across runs.

### Normalization

Before hashing, names are normalized:

1. Convert to lowercase
2. Strip whitespace
3. Generate UUID5 hash
4. Take first 8 hex characters

```python
normalized = author.strip().lower()
author_uuid = uuid.uuid5(NAMESPACE_AUTHOR, normalized)
return author_uuid.hex[:8]  # First 8 chars
```

## Testing

Run the test suite:

```bash
python test_anonymization.py
```

This validates:
- ✅ Author anonymization is deterministic
- ✅ Mentions are properly replaced
- ✅ Table operations work correctly
- ✅ No PII leaks in output

## Privacy by Design

Anonymization is **not optional** and happens automatically:

1. **Early application**: Anonymization at parse time
2. **No raw data downstream**: Agents never see real names
3. **Deterministic**: Same author → same pseudonym
4. **Immutable**: Once anonymized, original names are lost

This ensures privacy-by-design throughout the entire pipeline.
