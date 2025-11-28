# Refactoring Plan: Privacy as Adapter-Specific Strategy

## Context

Privacy should be a **data source concern**, not a core pipeline concern. Each adapter should decide its own privacy strategy based on the nature of the data:

- **Private data** (WhatsApp, Slack) → Anonymize before returning
- **Public data** (judicial records, news feeds) → Return as-is
- **Mixed data** → Adapter decides based on metadata

This keeps the core pipeline clean and adapter-focused.

## Current State (What We Built)

✅ Privacy configuration in `config/settings.py`:
- `PrivacySettings` with `enabled`, `pii_action`, `anonymize_authors`
- Config validation and warnings

✅ Privacy functions support configuration:
- `anonymize_table(table, enabled=bool)`
- `validate_text_privacy(text, action=..., enabled=bool)`

✅ Privacy is currently applied in:
- `input_adapters/whatsapp/parsing.py:356` - Calls `anonymize_table()`
- Pipeline assumes privacy is handled

## Proposed Architecture

### 1. Privacy as Adapter Responsibility

```
┌─────────────────────────────────────────────┐
│  InputAdapter Protocol                      │
│  - parse() returns already-processed data   │
│  - Each adapter chooses privacy strategy    │
└─────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌──────────────────┐  ┌──────────────────────┐
│ WhatsAppAdapter  │  │ IperonTjroAdapter    │
│ (Private Data)   │  │ (Public Data)        │
│                  │  │                      │
│ ✅ Anonymizes    │  │ ❌ No anonymization  │
│ ✅ PII detection │  │ ✅ Returns raw data  │
└──────────────────┘  └──────────────────────┘
```

### 2. Core Pipeline Changes

**Remove:**
- Privacy enforcement from pipeline orchestration
- Assumptions that all data is anonymized
- Global privacy gates

**Keep:**
- Privacy utilities in `egregora.privacy.*` (for adapters to use)
- Privacy config in `.egregora/config.yml` (for adapters to read)
- Existing privacy functions (adapters can call them)

### 3. Adapter Privacy Strategies

Each adapter implements privacy in `parse()`:

```python
class WhatsAppAdapter(InputAdapter):
    """Private conversation data - needs anonymization."""

    def parse(self, input_path: Path, **kwargs) -> Table:
        # 1. Parse raw data
        raw_table = parse_source(export, expose_raw_author=True)

        # 2. Load privacy config for this adapter
        privacy_config = self._get_privacy_config()

        # 3. Apply privacy if enabled
        if privacy_config.enabled and privacy_config.anonymize_authors:
            raw_table = anonymize_table(
                raw_table,
                enabled=privacy_config.anonymize_authors
            )

        return raw_table
```

```python
class IperonTjroAdapter(InputAdapter):
    """Public judicial records - no anonymization."""

    def parse(self, input_path: Path, **kwargs) -> Table:
        # Parse and return as-is (public data)
        return parse_judicial_records(input_path)
        # No anonymization - judge names, case numbers are public
```

## Implementation Plan

### Phase 1: Adapter Privacy Infrastructure (30 min)

**Add privacy accessor to InputAdapter base:**

```python
# input_adapters/base.py

class InputAdapter(Protocol):
    """Base adapter protocol."""

    def get_privacy_strategy(self) -> PrivacyStrategy:
        """Return this adapter's privacy strategy.

        Returns:
            PrivacyStrategy enum: ANONYMIZE, NONE, or CUSTOM
        """
        return PrivacyStrategy.NONE  # Default: no privacy (public data)

    def should_anonymize_authors(self, config: EgregoraConfig) -> bool:
        """Check if this adapter should anonymize authors.

        Adapters can override to implement custom logic.
        Default respects config.privacy.enabled.
        """
        return config.privacy.enabled and config.privacy.anonymize_authors
```

**Add PrivacyStrategy enum:**

```python
# constants.py

class PrivacyStrategy(str, Enum):
    """Privacy handling strategies for adapters."""

    ANONYMIZE = "anonymize"  # Full privacy (WhatsApp, Slack)
    NONE = "none"           # Public data (judicial, news)
    CUSTOM = "custom"       # Adapter-specific logic
```

### Phase 2: Update WhatsAppAdapter (30 min)

**Make privacy configurable:**

```python
# input_adapters/whatsapp/adapter.py

class WhatsAppAdapter(InputAdapter):
    """Private conversation adapter with configurable privacy."""

    def __init__(self, *, config: EgregoraConfig | None = None):
        self._config = config

    def get_privacy_strategy(self) -> PrivacyStrategy:
        return PrivacyStrategy.ANONYMIZE  # Always anonymize private chats

    def parse(self, input_path: Path, **kwargs) -> Table:
        # Parse messages
        messages = parse_source(export, expose_raw_author=True)

        # Apply privacy based on config
        if self._should_apply_privacy():
            messages = anonymize_table(
                messages,
                enabled=self._config.privacy.anonymize_authors
            )

        return messages

    def _should_apply_privacy(self) -> bool:
        """Check if privacy should be applied."""
        if not self._config:
            return True  # Default: always anonymize
        return self._config.privacy.enabled
```

### Phase 3: Update IperonTjroAdapter (15 min)

**Document that it's public data:**

```python
# input_adapters/iperon_tjro.py

class IperonTjroAdapter(InputAdapter):
    """Brazilian judicial records adapter (PUBLIC DATA).

    No privacy applied - all data is public record:
    - Judge names are public officials
    - Case numbers are public identifiers
    - Legal proceedings are public information
    """

    def get_privacy_strategy(self) -> PrivacyStrategy:
        return PrivacyStrategy.NONE  # Public data, no anonymization

    def parse(self, input_path: Path, **kwargs) -> Table:
        # Return raw public data
        return parse_judicial_feed(input_path)
        # No anonymization needed
```

### Phase 4: Remove Privacy from Pipeline (20 min)

**Remove core pipeline privacy assumptions:**

1. Remove privacy validation from `orchestration/write_pipeline.py`
2. Document that adapters handle privacy
3. Update CLAUDE.md to reflect new architecture

```python
# orchestration/write_pipeline.py

def run(params: PipelineRunParams):
    """Run write pipeline.

    NOTE: Privacy is handled by input adapters.
    Each adapter decides its own privacy strategy:
    - WhatsApp: anonymizes authors
    - Judicial records: public data, no anonymization
    - Self: already processed
    """
    # Get adapter (privacy handled internally)
    adapter = get_adapter(params.source_type)

    # Parse returns already-processed data
    messages = adapter.parse(params.input_path)
    # No privacy gate here - adapter already handled it
```

### Phase 5: Update Configuration Documentation (15 min)

**Update `docs/features/privacy.md`:**

```markdown
# Privacy Architecture

Privacy in Egregora is **adapter-specific**. Each data source decides
its own privacy strategy:

## Privacy by Data Source

### Private Data (Anonymized)
- **WhatsApp exports** - Full anonymization
- **Slack exports** - Full anonymization
- **Private archives** - Configurable

Configuration:
\`\`\`yaml
privacy:
  enabled: true           # Enable for private adapters
  anonymize_authors: true # Replace names with UUIDs
  pii_detection_enabled: true
\`\`\`

### Public Data (No Anonymization)
- **Judicial records** (iperon-tjro) - Public officials, no privacy
- **News feeds** - Public information
- **Academic papers** - Published content

No configuration needed - adapters return data as-is.

## How It Works

1. **Adapter decides** - Each InputAdapter chooses privacy strategy
2. **Privacy applied in parse()** - Before data reaches pipeline
3. **Core is agnostic** - Pipeline doesn't know/care about privacy
4. **Config is optional** - Adapters can use privacy config or ignore it
```

### Phase 6: Update CLAUDE.md (15 min)

**Update architecture section:**

```markdown
## Privacy Architecture

Privacy is an **adapter-level concern**, not a pipeline concern:

- **Private data adapters** (WhatsApp, Slack) anonymize before returning data
- **Public data adapters** (judicial, news) return raw data
- **Core pipeline** is privacy-agnostic

### Privacy Flow

\`\`\`
InputAdapter.parse()
  ├─ Parse raw data
  ├─ Check adapter privacy strategy
  ├─ Apply anonymization if needed (private data only)
  └─ Return processed table
      ↓
Pipeline (privacy-agnostic)
  ├─ Receives clean data
  └─ No privacy assumptions
\`\`\`

### Per-Adapter Privacy

| Adapter | Privacy Strategy | Reason |
|---------|-----------------|--------|
| WhatsApp | ANONYMIZE | Private conversations |
| Slack | ANONYMIZE | Private workplace chat |
| Iperon-TJRO | NONE | Public judicial records |
| Self-reflection | NONE | Already processed |
| News feeds | NONE | Public information |
```

## Migration Guide

### For Existing Code

**Before (privacy in pipeline):**
```python
# Pipeline enforces privacy
raw_data = adapter.parse(path)
anonymized = anonymize_table(raw_data)  # Pipeline does this
```

**After (privacy in adapter):**
```python
# Adapter handles privacy internally
data = adapter.parse(path)  # Already anonymized if needed
# Pipeline just uses data as-is
```

### For Custom Adapters

**Creating a private data adapter:**
```python
class MyPrivateAdapter(InputAdapter):
    def get_privacy_strategy(self) -> PrivacyStrategy:
        return PrivacyStrategy.ANONYMIZE

    def parse(self, input_path: Path, **kwargs) -> Table:
        data = parse_my_format(input_path)

        # Apply privacy using egregora utilities
        config = load_egregora_config(Path("."))
        if config.privacy.enabled:
            data = anonymize_table(data, enabled=True)

        return data
```

**Creating a public data adapter:**
```python
class MyPublicAdapter(InputAdapter):
    def get_privacy_strategy(self) -> PrivacyStrategy:
        return PrivacyStrategy.NONE

    def parse(self, input_path: Path, **kwargs) -> Table:
        # Just parse and return - no privacy needed
        return parse_public_records(input_path)
```

## Testing Strategy

### New Tests

1. **Test WhatsApp adapter respects privacy config:**
   - `privacy.enabled=true` → anonymizes
   - `privacy.enabled=false` → returns raw (for testing)

2. **Test public adapters ignore privacy:**
   - IperonTjro always returns raw data
   - Self-reflection returns as-is

3. **Test adapter privacy strategies:**
   - Each adapter reports correct strategy
   - Strategy affects pipeline behavior

### Existing Tests

- All existing privacy function tests still work (functions unchanged)
- Config tests still valid (config still exists)
- Just update integration tests that assumed pipeline anonymizes

## Benefits

✅ **Cleaner separation of concerns** - Privacy is data source decision
✅ **Enables public datasets** - No forced anonymization
✅ **Flexible architecture** - Each adapter chooses strategy
✅ **Backward compatible** - Existing privacy code still works
✅ **Config still useful** - Private adapters can use it
✅ **No wasted work** - Our privacy implementation is reused by adapters

## Non-Goals

❌ Don't remove privacy utilities (`egregora.privacy.*`) - adapters need them
❌ Don't remove privacy config - private adapters use it
❌ Don't change privacy function signatures - just built them!
❌ Don't break existing WhatsApp adapter - just refactor internally

## Implementation Order

1. Add `PrivacyStrategy` enum to constants.py
2. Add privacy methods to InputAdapter protocol
3. Update WhatsAppAdapter to handle privacy internally
4. Update IperonTjroAdapter to document public data
5. Remove privacy assumptions from pipeline
6. Update documentation
7. Add tests for adapter privacy strategies

**Estimated time:** ~2 hours

**Risk:** Low - mostly refactoring, no behavior changes for WhatsApp

---

## Summary

This refactoring makes privacy **adapter-specific** while keeping all the
work we just did. Privacy config, functions, and tests are still used -
just by adapters instead of the core pipeline.

The core pipeline becomes simpler and adapters gain flexibility to handle
privacy appropriately for their data source.
