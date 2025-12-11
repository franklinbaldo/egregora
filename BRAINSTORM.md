# Egregora Brainstorm: Ideas from Open PRs

This document captures valuable ideas and concepts from PRs that were closed due to conflicts or scope issues, but whose underlying intentions are worth preserving for future development.

---

## 1. WhatsApp Parser Performance Optimization
**Source:** PR #1188 (Bolt: Add caching to WhatsApp parser)

### Idea
Add `functools.lru_cache` to frequently-called date/time parsing functions in WhatsApp adapter.

### Rationale
- WhatsApp chat logs contain thousands of messages with repeated date strings
- `dateutil.parser` is computationally expensive (uses heuristics to guess formats)
- Caching can reduce parsing operations from N (total messages) to D (unique days)

### Implementation Concept
```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def _parse_message_date(date_str: str) -> date:
    return dateutil.parser.parse(date_str).date()

@lru_cache(maxsize=256)
def _parse_message_time(time_str: str) -> time:
    return dateutil.parser.parse(time_str).time()
```

### Priority: Medium
Good performance win for large chat exports.

---

## 2. Unified Content Structure with Categories
**Source:** PR #1183 (Unify documents into single posts folder)

### Idea
Put all document types (posts, profiles, journal, enrichment) in a single `posts/` folder and differentiate using MkDocs Material's category feature.

### Rationale
- Simpler file structure - one folder for all content
- Leverages MkDocs Material's built-in category navigation
- Reduces path handling complexity

### Implementation Concept
```yaml
# Each document type gets a category
categories:
  - Posts (default)
  - Authors (profiles)
  - Journal (journal entries)
  - Enrichment (URL summaries, media descriptions)
```

### Considerations
- Need slug prefixing to avoid collisions (`profile-uuid`, `journal-label`)
- URL structure changes (SEO impact)
- Category filtering in nav configuration

### Priority: Low
Interesting architectural choice but current structure works well.

---

## 3. Agent Read Status Tracking
**Source:** PR #1169 (Unified Entries Table and Agent Read Status)

### Idea
Track which agents have read which entries, enabling multi-agent workflows where agents only process new content.

### Rationale
- Prevents reprocessing of already-handled content
- Enables agent "memory" across runs
- Supports incremental processing

### Implementation Concept
```sql
CREATE TABLE agent_read_status (
    agent_id VARCHAR,
    entry_id VARCHAR,
    read_at TIMESTAMP,
    PRIMARY KEY (agent_id, entry_id)
);
```

### Additional Idea: Feed ID
Add `feed_id` to Entry model to group entries by source (e.g., "whatsapp-export-1", "twitter-archive-2").

### Priority: High
Essential for v3 multi-agent architecture.

---

## 4. Demo Generation Automation
**Source:** PRs #1163, #1166, #1162

### Idea
Automated script to regenerate demo blog content via CLI, integrated into CI for validation.

### Rationale
- Ensures demo site always works with current codebase
- Catches regressions in blog generation pipeline
- Provides template for new users

### Implementation Concept
```python
# dev_tools/generate_demo.py
def generate_demo():
    # 1. Validate API key upfront (fail-fast)
    # 2. Create temp directory
    # 3. Run egregora init + write
    # 4. Verify output structure
    # 5. Optionally build and serve
```

### Priority: Medium
Good for CI/CD and onboarding.

---

## 5. Upfront API Key Validation
**Source:** PR #1162 (Gemini API key validation)

### Idea
Validate Gemini API key at startup before running expensive operations.

### Rationale
- Fail fast with clear error message
- Avoid deep pipeline failures with cryptic errors
- Better UX for new users

### Implementation Concept
```python
def validate_gemini_key(api_key: str) -> None:
    """Validate API key with lightweight count_tokens call."""
    try:
        client = genai.GenerativeModel('gemini-1.5-flash')
        client.count_tokens("test")
    except Exception as e:
        raise ValueError(f"Invalid Gemini API key: {e}")
```

### Priority: High
Simple improvement with significant UX benefit.

---

## 6. Enhanced Embedding Error Reporting
**Source:** PR #1162

### Idea
Capture and bubble up detailed API error text when embedding requests fail.

### Current Problem
Embedding failures show generic HTTP errors without the actual API response.

### Implementation Concept
```python
try:
    response = client.embed(...)
except httpx.HTTPStatusError as e:
    # Parse and include response body in error
    error_detail = e.response.text or e.response.json()
    raise EmbeddingError(f"Embedding failed: {error_detail}") from e
```

### Priority: High
Critical for debugging API issues.

---

## 7. Blog as Homepage Default
**Source:** PR #1163

### Idea
Set the generated blog feed as the homepage instead of a static landing page.

### Rationale
- Users want to see content immediately
- Blog feed is the primary value of the generated site
- Static landing pages often feel empty

### Implementation Concept
```yaml
# mkdocs.yml
nav:
  - Home: index.md  # This IS the blog feed
  # OR redirect index to posts/
```

### Priority: Low
User preference - can be configured.

---

## 8. Relative URL Generation
**Source:** PR #1168

### Idea
Enforce relative URL generation for all internal links to improve portability.

### Rationale
- Sites can be deployed to any path (not just root)
- Works offline / locally
- Easier testing

### Current State
Already partially implemented in URL conventions.

### Priority: Low
Already addressed in current implementation.

---

## Summary: Implementation Priorities

### High Priority (Should implement soon)
1. **API key validation** - Simple, high UX impact
2. **Enhanced embedding errors** - Critical for debugging
3. **Agent read status** - Essential for v3

### Medium Priority (Good to have)
4. **Parser caching** - Performance win
5. **Demo generation** - CI/CD improvement

### Low Priority (Consider later)
6. **Unified content structure** - Architectural change
7. **Blog as homepage** - User preference
8. **Relative URLs** - Already addressed

---

*Generated: 2025-12-11*
*Source: Open PR review session*
