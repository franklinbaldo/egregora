# Privacy Architecture: Granular Column-Level Strategies

## Key Insight: LLM-Native PII Detection

**LLMs don't need regex patterns to identify PII - they just know.**

Instead of maintaining complex pattern libraries, we leverage LLM's natural understanding:
- ✅ Tell the LLM what we consider PII (declarative)
- ✅ Or let the LLM decide using its judgment
- ❌ No regex pattern maintenance
- ❌ No brittle pattern matching

This applies to **all LLM outputs**:
- Blog posts (main output)
- Agent execution journals (thinking logs)
- Tool call results

## Two-Level Privacy Model

### Level 1: Adapter Structural Anonymization (Pre-Pipeline)
**What**: Anonymize raw data columns before entering pipeline
**Where**: `InputAdapter.parse()`
**Configurable**: Per-adapter, per-column strategies
**Examples**:
- Author names → UUID mapping or full redaction
- Mentions in text → Replace with UUIDs or `[MENTION]`
- Phone numbers → Redact or keep

### Level 2: LLM-Native PII Prevention (In-Pipeline)
**What**: Instruct LLMs to avoid generating PII using their native understanding
**Where**: All agent prompts (writer, enricher, banner) + agent journals
**How**: Declarative specification - tell LLM what we consider PII, or let it decide
**No regex needed**: LLMs naturally understand what constitutes PII
**Configurable**: Global on/off switch + optional PII type specification
**Examples**:
- "Do not include contact information (phone, email, address)"
- "Replace specific names with generic references"
- "Avoid reproducing personal identifying information"
- **Critical**: Applies to ALL outputs including execution journals

## Configuration Schema

```yaml
privacy:
  # Level 1: Structural anonymization (adapter-level)
  structural:
    enabled: true
    author_strategy: uuid_mapping  # uuid_mapping, full_redaction, role_based, none
    mention_strategy: uuid_replacement  # uuid_replacement, generic_redaction, role_based, none
    phone_strategy: redact  # redact, hash, none
    email_strategy: redact  # redact, hash, none

  # Level 2: LLM-native PII prevention (per-agent)
  pii_prevention:
    enricher:
      enabled: true
      scope: contact_info  # What to protect: contact_info, all_pii, or custom definition

    writer:
      enabled: true
      scope: all_pii  # Broader protection for public blog posts
      apply_to_journals: true  # CRITICAL: Also protect agent execution journals

    banner:
      enabled: false  # Image generation typically doesn't expose PII

    reader:
      enabled: false  # Reader only evaluates, doesn't generate new content
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

### PII in Text (Structural Pre-Processing Only)

**Note**: Structural PII handling uses simple regex for deterministic preprocessing.
For LLM outputs, we rely on LLM-native understanding (Level 2).

**Strategy Options**:

```python
class TextPIIStrategy(str, Enum):
    """How to handle PII in raw text during structural preprocessing."""

    REDACT = "redact"      # 555-1234 → [PHONE] (deterministic)
    HASH = "hash"          # 555-1234 → PHONE_a3f8b9 (deterministic)
    NONE = "none"          # 555-1234 → 555-1234 (public data)
```

**Important**: These strategies are for INPUT preprocessing only. LLM outputs use
natural language instructions, not regex patterns.

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

## LLM-Native PII Prevention (No Regex Patterns)

### Core Principle

**LLMs naturally understand PII** - we don't need regex patterns to detect it.
We just tell the LLM what we consider private, or let it decide based on context.

### Privacy Scopes

```python
class PIIScope(str, Enum):
    """What PII to protect in LLM outputs."""

    CONTACT_INFO = "contact_info"  # Phone, email, address, URLs with personal info
    ALL_PII = "all_pii"            # Contact + names, ages, locations, etc.
    CUSTOM = "custom"              # User-defined specification
    LLM_DECIDE = "llm_decide"      # Let LLM use its judgment
```

### Dynamic Prompt Instructions

**Writer prompt (with journal protection)**:
```jinja
{# writer.jinja #}
You are a blog post writer...

{% if pii_prevention.enabled %}
CRITICAL PRIVACY REQUIREMENT:
You must not include personally identifying information in ANY output:
- Blog post content (main output)
- Agent execution journals (thinking logs)
- Tool call results or intermediate outputs

{% if pii_prevention.scope == "contact_info" %}
Specifically avoid: phone numbers, email addresses, physical addresses, personal URLs
{% elif pii_prevention.scope == "all_pii" %}
Avoid ALL personally identifying information including names, contact details,
ages, specific locations, or any data that could identify individuals
{% elif pii_prevention.scope == "custom" %}
{{ pii_prevention.custom_definition }}
{% else %}  {# llm_decide #}
Use your best judgment to avoid exposing personal information that could
identify or contact individuals
{% endif %}

Use generic references or anonymized identifiers when discussing people or entities.
{% endif %}

Your task: Write a blog post from this conversation...
```

**Enrichment prompt**:
```jinja
{# enricher.jinja #}
Analyze this URL/media and provide a summary...

{% if pii_prevention.enabled %}
PRIVACY: Do not include {% if pii_prevention.scope == "contact_info" %}
contact information (phone, email, address)
{% elif pii_prevention.scope == "all_pii" %}
any personally identifying information
{% else %}
personal details that could identify individuals
{% endif %} in your summary.
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
    pii_settings = config.privacy.pii_prevention.writer

    return {
        "conversation_xml": conversation_xml,
        "custom_instructions": config.writer.custom_instructions,
        "pii_prevention": {
            "enabled": pii_settings.enabled,
            "scope": pii_settings.scope,
            "custom_definition": pii_settings.custom_definition if pii_settings.scope == "custom" else None,
            "apply_to_journals": pii_settings.apply_to_journals,
        }
    }

# agents/enricher.py

def _build_enricher_context(
    content: str,
    config: EgregoraConfig,
) -> dict:
    """Build context for enricher prompt."""
    pii_settings = config.privacy.pii_prevention.enricher

    return {
        "content": content,
        "pii_prevention": {
            "enabled": pii_settings.enabled,
            "scope": pii_settings.scope,
            "custom_definition": pii_settings.custom_definition if pii_settings.scope == "custom" else None,
        }
    }
```

### Configuration Models

```python
# config/settings.py

class PIIScope(str, Enum):
    """What PII to protect in LLM outputs (LLM-native understanding)."""

    CONTACT_INFO = "contact_info"  # Phone, email, address, personal URLs
    ALL_PII = "all_pii"            # Contact + names, ages, locations, identifiers
    CUSTOM = "custom"              # User-defined specification
    LLM_DECIDE = "llm_decide"      # Let LLM use its judgment


class AgentPIISettings(BaseModel):
    """PII prevention settings for a specific agent (LLM-native)."""

    enabled: bool = Field(
        default=True,
        description="Enable PII prevention for this agent"
    )
    scope: PIIScope = Field(
        default=PIIScope.CONTACT_INFO,
        description="What PII to protect (LLM understands these categories natively)"
    )
    custom_definition: str | None = Field(
        default=None,
        description="Custom PII definition (when scope=custom). LLM will interpret this."
    )
    apply_to_journals: bool = Field(
        default=True,
        description="Also protect agent execution journals (not just main output)"
    )


class PIIPreventionSettings(BaseModel):
    """LLM-native PII prevention settings for all agents."""

    enricher: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=True,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,  # Enricher journals typically internal
        ),
        description="Enricher agent PII prevention"
    )

    writer: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=True,
            scope=PIIScope.ALL_PII,
            apply_to_journals=True,  # CRITICAL: protect journals too
        ),
        description="Writer agent PII prevention"
    )

    banner: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=False,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,
        ),
        description="Banner agent PII prevention (image generation)"
    )

    reader: AgentPIISettings = Field(
        default_factory=lambda: AgentPIISettings(
            enabled=False,
            scope=PIIScope.CONTACT_INFO,
            apply_to_journals=False,
        ),
        description="Reader agent PII prevention (typically disabled)"
    )


class StructuralPrivacySettings(BaseModel):
    """Structural anonymization (adapter-level)."""

    enabled: bool = Field(default=True, description="Enable structural anonymization")
    author_strategy: str = Field(default="uuid_mapping", description="Author anonymization strategy")
    mention_strategy: str = Field(default="uuid_replacement", description="Mention handling strategy")
    phone_strategy: str = Field(default="redact", description="Phone number handling")
    email_strategy: str = Field(default="redact", description="Email handling")


class PrivacySettings(BaseModel):
    """Privacy configuration (two-level model)."""

    structural: StructuralPrivacySettings = Field(
        default_factory=StructuralPrivacySettings,
        description="Structural anonymization settings (adapter-level)"
    )

    pii_prevention: PIIPreventionSettings = Field(
        default_factory=PIIPreventionSettings,
        description="PII prevention in LLM outputs (per-agent)"
    )

    # Backward compatibility
    @property
    def enabled(self) -> bool:
        """Legacy: overall privacy enabled."""
        return self.structural.enabled
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

  pii_prevention:
    enricher:
      enabled: true
      scope: all_pii  # Comprehensive protection
    writer:
      enabled: true
      scope: all_pii
      apply_to_journals: true  # Protect journals too
    banner:
      enabled: false
    reader:
      enabled: false
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

  pii_prevention:
    enricher:
      enabled: true
      scope: contact_info  # Just contact details
    writer:
      enabled: true
      scope: contact_info
      apply_to_journals: true
    banner:
      enabled: false
    reader:
      enabled: false
```

### No Privacy (Public Data)

```yaml
privacy:
  structural:
    enabled: false  # No column anonymization

  pii_prevention:
    enricher:
      enabled: false
    writer:
      enabled: false
    banner:
      enabled: false
    reader:
      enabled: false
```

### Public Data with PII Protection

```yaml
# Judicial records: public names OK, but don't generate NEW PII
privacy:
  structural:
    enabled: false  # Judge names, parties are public

  pii_prevention:
    enricher:
      enabled: true
      scope: contact_info  # Don't add contact info to descriptions
    writer:
      enabled: true
      scope: contact_info  # Don't add contact info to blog posts
      apply_to_journals: true
    banner:
      enabled: false
    reader:
      enabled: false
```

### Custom PII Definition

```yaml
# Let LLM decide what's sensitive based on custom guidelines
privacy:
  structural:
    enabled: true
    author_strategy: uuid_mapping

  pii_prevention:
    enricher:
      enabled: true
      scope: custom
      custom_definition: |
        Avoid sharing: case numbers, badge numbers, license plates,
        medical record numbers, or other government-issued identifiers
    writer:
      enabled: true
      scope: custom
      custom_definition: |
        Do not include identifiers like case numbers, badge numbers,
        or medical records. Names of public officials are OK.
      apply_to_journals: true
    banner:
      enabled: false
    reader:
      enabled: false
```

### Let LLM Decide

```yaml
# Trust LLM to make judgment calls about what's sensitive
privacy:
  structural:
    enabled: true
    author_strategy: uuid_mapping

  pii_prevention:
    enricher:
      enabled: true
      scope: llm_decide  # LLM uses its judgment
    writer:
      enabled: true
      scope: llm_decide
      apply_to_journals: true
    banner:
      enabled: false
    reader:
      enabled: false
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

Two-level privacy model with **LLM-native PII understanding**:

### 1. Structural (Adapter - Deterministic Preprocessing)
Column-level anonymization strategies using simple regex:
- Author: UUID, redaction, roles, or none
- Mentions: UUID, redaction, roles, or none
- PII patterns: Redact, hash, or keep
- **Purpose**: Deterministic preprocessing of raw input data

### 2. LLM-Native PII Prevention (Agent Prompts - No Regex Needed)
Natural language instructions that leverage LLM's understanding of PII:
- **No regex patterns required** - LLMs natively understand what constitutes PII
- **Scope-based**: Tell LLM what we consider private (`contact_info`, `all_pii`, `custom`, `llm_decide`)
- **Simple specification**: Declarative instructions in natural language
- **Journal protection**: CRITICAL - applies to agent execution journals, not just main outputs
- **Flexible**: Can use custom definitions or let LLM use its judgment

### Key Advantages

✅ **Simpler architecture** - No pattern maintenance, LLM handles understanding
✅ **More robust** - LLMs recognize PII variants humans might miss
✅ **Flexible** - Easy to customize what counts as PII
✅ **Comprehensive** - Protects ALL agent outputs including journals
✅ **Separation of concerns** - Structural preprocessing vs. LLM output protection
✅ **Backward compatible** - Defaults match current behavior

This approach leverages LLM capabilities instead of fighting them with regex patterns.
