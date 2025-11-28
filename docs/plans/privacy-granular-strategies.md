# Privacy Architecture: Granular Column-Level Strategies

## Two-Level Privacy Model

### Level 1: Adapter Structural Anonymization (Pre-Pipeline)
**What**: Anonymize raw data columns before entering pipeline
**Where**: `InputAdapter.parse()`
**Configurable**: Per-adapter, per-column strategies
**Examples**:
- Author names → UUID mapping or full redaction
- Mentions in text → Replace with UUIDs or `[MENTION]`
- Phone numbers → Redact or keep

### Level 2: Core Content PII Prevention (In-Pipeline)
**What**: Instruct LLMs to avoid generating PII
**Where**: Prompt templates (writer, enricher)
**Configurable**: Global on/off switch
**Examples**:
- "Do not include phone numbers in summaries"
- "Replace specific names with generic references"
- "Avoid reproducing contact information"

## Configuration Schema

```yaml
privacy:
  # Level 1: Structural anonymization (adapter-level)
  structural:
    enabled: true
    author_strategy: uuid_mapping  # uuid_mapping, full_redaction, none
    mention_strategy: uuid_replacement  # uuid_replacement, generic_redaction, none
    phone_strategy: redact  # redact, none
    email_strategy: redact  # redact, none

  # Level 2: Content PII prevention (prompt-level)
  content:
    enabled: true  # Include PII prevention in prompts
    instruction_mode: strict  # strict, relaxed, none
```

## Column-Level Privacy Strategies

### Author Columns

**Strategy Options**:

```python
class AuthorPrivacyStrategy(str, Enum):
    """How to handle author identification."""

    UUID_MAPPING = "uuid_mapping"      # Alice → 550e8400-e29b-41d4-a716...
    FULL_REDACTION = "full_redaction"  # Alice → [AUTHOR]
    ROLE_BASED = "role_based"          # Alice → Participant_1
    NONE = "none"                      # Alice → Alice (public data)
```

**Implementation**:

```python
# WhatsApp adapter with configurable author strategy
class WhatsAppAdapter:
    def _anonymize_authors(self, table: Table, strategy: AuthorPrivacyStrategy) -> Table:
        if strategy == AuthorPrivacyStrategy.UUID_MAPPING:
            # Current behavior: deterministic UUID mapping
            return anonymize_table(table, enabled=True)

        elif strategy == AuthorPrivacyStrategy.FULL_REDACTION:
            # Aggressive: replace all with generic token
            return table.mutate(
                author_raw=ibis.literal("[AUTHOR]"),
                author=ibis.literal("[AUTHOR]")
            )

        elif strategy == AuthorPrivacyStrategy.ROLE_BASED:
            # Sequential: Participant_1, Participant_2, etc.
            return self._assign_participant_ids(table)

        else:  # NONE
            return table
```

### Mention Columns (Inside Text)

**Strategy Options**:

```python
class MentionPrivacyStrategy(str, Enum):
    """How to handle @mentions in text."""

    UUID_REPLACEMENT = "uuid_replacement"  # @Alice → @550e8400...
    GENERIC_REDACTION = "generic_redaction"  # @Alice → @[MENTION]
    ROLE_BASED = "role_based"  # @Alice → @Participant_1
    NONE = "none"  # @Alice → @Alice
```

**Implementation**:

```python
def _anonymize_mentions(self, text: str, strategy: MentionPrivacyStrategy) -> str:
    """Anonymize @mentions based on strategy."""
    if strategy == MentionPrivacyStrategy.UUID_REPLACEMENT:
        # Current: map to UUID
        return _sanitize_mentions(text, self.author_uuid_mapping)

    elif strategy == MentionPrivacyStrategy.GENERIC_REDACTION:
        # Replace all with generic token
        return MENTION_PATTERN.sub("[MENTION]", text)

    elif strategy == MentionPrivacyStrategy.ROLE_BASED:
        # Map to participant IDs
        return self._replace_mentions_with_roles(text)

    else:  # NONE
        return text
```

### PII in Text (Phones, Emails)

**Strategy Options**:

```python
class TextPIIStrategy(str, Enum):
    """How to handle PII patterns in text content."""

    REDACT = "redact"      # 555-1234 → [PHONE]
    HASH = "hash"          # 555-1234 → PHONE_a3f8b9
    NONE = "none"          # 555-1234 → 555-1234
```

## Adapter Privacy Configuration

### Per-Adapter Configuration

```python
@dataclass
class AdapterPrivacyConfig:
    """Privacy configuration for a specific adapter."""

    # Structural anonymization
    author_strategy: AuthorPrivacyStrategy = AuthorPrivacyStrategy.UUID_MAPPING
    mention_strategy: MentionPrivacyStrategy = MentionPrivacyStrategy.UUID_REPLACEMENT
    phone_strategy: TextPIIStrategy = TextPIIStrategy.REDACT
    email_strategy: TextPIIStrategy = TextPIIStrategy.REDACT

    @classmethod
    def from_egregora_config(cls, config: EgregoraConfig) -> AdapterPrivacyConfig:
        """Build from global config."""
        structural = config.privacy.structural
        return cls(
            author_strategy=AuthorPrivacyStrategy(structural.author_strategy),
            mention_strategy=MentionPrivacyStrategy(structural.mention_strategy),
            phone_strategy=TextPIIStrategy(structural.phone_strategy),
            email_strategy=TextPIIStrategy(structural.email_strategy),
        )
```

### WhatsApp Adapter Implementation

```python
class WhatsAppAdapter(InputAdapter):
    """Private conversation adapter with granular privacy."""

    def __init__(self, config: EgregoraConfig | None = None):
        self._config = config
        self._privacy_config = (
            AdapterPrivacyConfig.from_egregora_config(config)
            if config and config.privacy.structural.enabled
            else AdapterPrivacyConfig(
                author_strategy=AuthorPrivacyStrategy.NONE,
                mention_strategy=MentionPrivacyStrategy.NONE,
                phone_strategy=TextPIIStrategy.NONE,
                email_strategy=TextPIIStrategy.NONE,
            )
        )

    def parse(self, input_path: Path, **kwargs) -> Table:
        # 1. Parse raw messages
        messages = parse_source(export, expose_raw_author=True)

        # 2. Apply column-level privacy
        if self._config and self._config.privacy.structural.enabled:
            messages = self._apply_privacy(messages)

        return messages

    def _apply_privacy(self, table: Table) -> Table:
        """Apply granular privacy strategies."""
        # Author anonymization
        table = self._anonymize_authors(
            table,
            self._privacy_config.author_strategy
        )

        # Text content anonymization
        table = self._anonymize_text_content(
            table,
            mention_strategy=self._privacy_config.mention_strategy,
            phone_strategy=self._privacy_config.phone_strategy,
            email_strategy=self._privacy_config.email_strategy,
        )

        return table
```

### Judicial Records Adapter (No Privacy)

```python
class IperonTjroAdapter(InputAdapter):
    """Public judicial records - no structural privacy needed."""

    def parse(self, input_path: Path, **kwargs) -> Table:
        # Public data - return as-is
        # Judge names, case numbers, parties are public record
        return parse_judicial_records(input_path)
```

## Content-Level PII Prevention (Prompts)

### Dynamic Prompt Instructions

**Current writer prompt (with PII prevention)**:
```jinja
{# writer.jinja #}
You are a blog post writer...

{% if privacy_content_enabled %}
IMPORTANT PRIVACY GUIDELINES:
- Do NOT include specific phone numbers, email addresses, or contact info
- Replace specific personal details with generic references
- Avoid reproducing verbatim quotes containing PII
- If discussing people, use anonymized references or roles
{% endif %}

Your task: Write a blog post from this conversation...
```

**Enrichment prompt**:
```jinja
{# enricher.jinja #}
Analyze this URL/media and provide a summary...

{% if privacy_content_enabled %}
PRIVACY: Do not include contact information or personal details in your summary.
{% endif %}
```

### Prompt Context Builder

```python
# agents/writer.py

def _build_prompt_context(
    conversation_xml: str,
    config: EgregoraConfig,
) -> dict:
    """Build context for writer prompt."""
    return {
        "conversation_xml": conversation_xml,
        "custom_instructions": config.writer.custom_instructions,
        "privacy_content_enabled": config.privacy.content.enabled,
        "privacy_mode": config.privacy.content.instruction_mode,
    }
```

### Configuration

```python
# config/settings.py

class StructuralPrivacySettings(BaseModel):
    """Structural anonymization (adapter-level)."""

    enabled: bool = Field(default=True, description="Enable structural anonymization")
    author_strategy: str = Field(default="uuid_mapping", description="Author anonymization strategy")
    mention_strategy: str = Field(default="uuid_replacement", description="Mention handling strategy")
    phone_strategy: str = Field(default="redact", description="Phone number handling")
    email_strategy: str = Field(default="redact", description="Email handling")


class ContentPrivacySettings(BaseModel):
    """Content PII prevention (prompt-level)."""

    enabled: bool = Field(
        default=True,
        description="Include PII prevention instructions in prompts"
    )
    instruction_mode: Literal["strict", "relaxed", "none"] = Field(
        default="strict",
        description="Strictness of PII prevention instructions"
    )


class PrivacySettings(BaseModel):
    """Privacy configuration (two-level model)."""

    structural: StructuralPrivacySettings = Field(
        default_factory=StructuralPrivacySettings,
        description="Structural anonymization settings"
    )
    content: ContentPrivacySettings = Field(
        default_factory=ContentPrivacySettings,
        description="Content PII prevention settings"
    )

    # Backward compatibility
    @property
    def enabled(self) -> bool:
        """Legacy: overall privacy enabled."""
        return self.structural.enabled or self.content.enabled
```

## Configuration Examples

### Maximum Privacy (Private Chats)

```yaml
privacy:
  structural:
    enabled: true
    author_strategy: full_redaction  # Most aggressive
    mention_strategy: generic_redaction
    phone_strategy: redact
    email_strategy: redact

  content:
    enabled: true
    instruction_mode: strict  # Strong LLM guidance
```

### Moderate Privacy (Semi-Public)

```yaml
privacy:
  structural:
    enabled: true
    author_strategy: uuid_mapping  # Current behavior
    mention_strategy: uuid_replacement
    phone_strategy: redact
    email_strategy: redact

  content:
    enabled: true
    instruction_mode: relaxed
```

### No Privacy (Public Data)

```yaml
privacy:
  structural:
    enabled: false

  content:
    enabled: false  # No PII prevention in prompts
```

### Public Data with Content Protection

```yaml
# Judicial records: public names OK, but don't generate new PII
privacy:
  structural:
    enabled: false  # Judge names, parties are public

  content:
    enabled: true  # Still prevent LLM from adding new PII
    instruction_mode: relaxed
```

## Migration Path

### Phase 1: Add Granular Config (1 hour)

1. Add new enums to `constants.py`:
   - `AuthorPrivacyStrategy`
   - `MentionPrivacyStrategy`
   - `TextPIIStrategy`

2. Update `PrivacySettings` in `config/settings.py`:
   - Add `structural` and `content` nested settings
   - Keep backward compatibility

3. Update default config:
   ```yaml
   privacy:
     structural:
       enabled: true
       author_strategy: uuid_mapping  # Current behavior
       mention_strategy: uuid_replacement
       phone_strategy: redact
       email_strategy: redact
     content:
       enabled: true
       instruction_mode: strict
   ```

### Phase 2: Adapter Privacy Logic (1.5 hours)

1. Create `AdapterPrivacyConfig` dataclass
2. Update `WhatsAppAdapter`:
   - Add `_privacy_config` attribute
   - Implement `_apply_privacy()` with strategies
   - Support all strategy types

3. Update `anonymize_table()` to support strategies:
   ```python
   def anonymize_table(
       table: Table,
       *,
       strategy: AuthorPrivacyStrategy = AuthorPrivacyStrategy.UUID_MAPPING,
   ) -> Table:
       if strategy == AuthorPrivacyStrategy.FULL_REDACTION:
           # Full redaction
       elif strategy == AuthorPrivacyStrategy.UUID_MAPPING:
           # Current behavior
       # ...
   ```

### Phase 3: Prompt Privacy Integration (1 hour)

1. Update prompt templates:
   - Add `{% if privacy_content_enabled %}` blocks
   - Add PII prevention instructions

2. Update agent context builders:
   - Pass `privacy_content_enabled` flag
   - Pass `privacy_mode` for instruction strictness

3. Update prompt manager to handle privacy context

### Phase 4: Testing (30 min)

1. Test structural strategies:
   - UUID mapping (current)
   - Full redaction
   - No privacy

2. Test content privacy:
   - Prompts with PII instructions
   - Prompts without (disabled)

3. Test adapter independence:
   - WhatsApp uses privacy
   - Judicial doesn't

## Benefits

✅ **Granular control** - Per-column privacy strategies
✅ **Flexible** - Adapters choose what fits their data
✅ **Separation of concerns** - Structural vs content privacy
✅ **Backward compatible** - Defaults match current behavior
✅ **Public data friendly** - Can disable structural but keep content protection
✅ **User choice** - Can disable content PII prevention if desired

## Summary

Two-level privacy model:

1. **Structural (Adapter)**: Column-level anonymization strategies
   - Author: UUID, redaction, roles, or none
   - Mentions: UUID, redaction, roles, or none
   - PII patterns: Redact, hash, or keep

2. **Content (Core)**: Prompt-level PII prevention
   - Dynamic instructions in prompts
   - Configurable strictness
   - Prevents LLM from generating new PII

This gives maximum flexibility while keeping concerns properly separated.
