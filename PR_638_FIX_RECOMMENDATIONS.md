# PR #638 Fix Recommendations

**Status**: Required before merge
**Priority**: P0 - Blocking
**Date**: 2025-11-10
**Estimated Effort**: 4-6 hours

## Executive Summary

PR #638 implements an excellent storage adapter pattern refactoring, but has two architectural issues:

1. **Bypassed existing OutputFormat abstraction** - Storage protocols are called directly instead of through the existing coordinator
2. **Missing data integrity validations** - Slug normalization, unique filename generation, and date prefix extraction were removed

This document provides step-by-step recommendations to fix both issues while preserving the excellent protocol design.

---

## Issue 1: Bypassed OutputFormat Coordinator

### Problem

The codebase already has a well-designed `OutputFormat` abstraction (in `src/egregora/rendering/base.py`) that coordinates all output format operations (MkDocs, Hugo, etc.). The storage adapter refactoring bypassed this coordinator and had agents call storage protocols directly.

**Current (incorrect) flow:**
```
WriterAgent → PostStorage/ProfileStorage (directly)
              ↓
              MkDocsPostStorage, MkDocsProfileStorage (duplicate coordination)
```

**Should be:**
```
WriterAgent → OutputFormat (MkDocs/Hugo/Database)
              ↓
              Provides: posts, profiles, journals (storage protocols)
              Coordinates: paths, scaffolding, validation
```

### Why This Matters

- **Duplication**: Path resolution, scaffolding logic duplicated between `OutputFormat` and storage implementations
- **Hard to extend**: Adding Database or S3 output requires duplicating all coordination logic
- **Breaks existing abstraction**: `OutputFormat` was designed to be the single coordinator
- **Registry pattern unused**: The `output_registry` auto-detection becomes useless

### Solution: Make OutputFormat Provide Storage Protocols

`OutputFormat` should **own** and **provide** the storage protocol implementations.

---

## Issue 2: Missing Data Integrity Validations

### Problem

The old `egregora.utils.write_post` utility performed critical validations that are now missing:

| Validation | Purpose | Impact if Missing |
|------------|---------|-------------------|
| `slugify()` | Normalize slugs to URL-safe format | Invalid filenames, broken URLs |
| Unique filename generation | Prevent overwrites | Silent data loss |
| Date prefix extraction | Organize files by date | Poor file organization |

**Note on PII validation**: Not needed at storage layer - anonymization happens before LLM processing, so LLM cannot generate PII. This was correctly removed.

### Solution: Add Validations to MkDocsPostStorage

Port the validation logic from `write_post.py` into `MkDocsPostStorage.write()`.

---

## Detailed Implementation Plan

### Phase 1: Add Storage Protocol Properties to OutputFormat

**File**: `src/egregora/rendering/base.py`

```python
from egregora.storage import PostStorage, ProfileStorage, JournalStorage, EnrichmentStorage

class OutputFormat(ABC):
    """Abstract base class for output formats.

    Output formats coordinate all storage operations for a specific
    site generator (MkDocs, Hugo, Jekyll, etc.) or backend (Database, S3).
    """

    # ... existing abstract methods (scaffold_site, resolve_paths, etc.) ...

    @property
    @abstractmethod
    def posts(self) -> PostStorage:
        """Get post storage implementation for this format.

        Returns:
            PostStorage implementation (MkDocs, Hugo, Database, etc.)
        """

    @property
    @abstractmethod
    def profiles(self) -> ProfileStorage:
        """Get profile storage implementation for this format.

        Returns:
            ProfileStorage implementation
        """

    @property
    @abstractmethod
    def journals(self) -> JournalStorage:
        """Get journal storage implementation for this format.

        Returns:
            JournalStorage implementation
        """

    @property
    @abstractmethod
    def enrichments(self) -> EnrichmentStorage:
        """Get enrichment storage implementation for this format.

        Returns:
            EnrichmentStorage implementation
        """

    @abstractmethod
    def initialize(self, site_root: Path) -> None:
        """Initialize storage implementations for a specific site.

        Args:
            site_root: Root directory of the site

        Note:
            Must be called before accessing storage properties.
            Creates necessary directories and sets up storage backends.
        """
```

### Phase 2: Implement Storage Properties in MkDocsOutputFormat

**File**: `src/egregora/rendering/mkdocs.py`

```python
from egregora.storage import PostStorage, ProfileStorage, JournalStorage, EnrichmentStorage
from egregora.storage.mkdocs import (
    MkDocsPostStorage,
    MkDocsProfileStorage,
    MkDocsJournalStorage,
    MkDocsEnrichmentStorage
)

class MkDocsOutputFormat(OutputFormat):
    """MkDocs output format with Material theme support.

    Coordinates all storage operations for MkDocs-based sites.
    """

    def __init__(self):
        self._site_root: Path | None = None
        self._posts_impl: PostStorage | None = None
        self._profiles_impl: ProfileStorage | None = None
        self._journals_impl: JournalStorage | None = None
        self._enrichments_impl: EnrichmentStorage | None = None

    def initialize(self, site_root: Path) -> None:
        """Initialize MkDocs storage implementations.

        Args:
            site_root: Root directory of the MkDocs site

        Side Effects:
            Creates all necessary directories (posts/, profiles/, etc.)
        """
        self._site_root = site_root

        # Create storage implementations
        self._posts_impl = MkDocsPostStorage(site_root)
        self._profiles_impl = MkDocsProfileStorage(site_root)
        self._journals_impl = MkDocsJournalStorage(site_root)
        self._enrichments_impl = MkDocsEnrichmentStorage(site_root)

    @property
    def posts(self) -> PostStorage:
        """Get MkDocs post storage implementation."""
        if self._posts_impl is None:
            raise RuntimeError("MkDocsOutputFormat not initialized - call initialize() first")
        return self._posts_impl

    @property
    def profiles(self) -> ProfileStorage:
        """Get MkDocs profile storage implementation."""
        if self._profiles_impl is None:
            raise RuntimeError("MkDocsOutputFormat not initialized - call initialize() first")
        return self._profiles_impl

    @property
    def journals(self) -> JournalStorage:
        """Get MkDocs journal storage implementation."""
        if self._journals_impl is None:
            raise RuntimeError("MkDocsOutputFormat not initialized - call initialize() first")
        return self._journals_impl

    @property
    def enrichments(self) -> EnrichmentStorage:
        """Get MkDocs enrichment storage implementation."""
        if self._enrichments_impl is None:
            raise RuntimeError("MkDocsOutputFormat not initialized - call initialize() first")
        return self._enrichments_impl

    # Update existing write_post to delegate to storage
    def write_post(self, content: str, metadata: dict[str, Any], output_dir: Path, **_kwargs: object) -> str:
        """Write a blog post in MkDocs format.

        Delegates to PostStorage implementation which handles validation,
        slug normalization, and unique filename generation.
        """
        if not self._posts_impl:
            raise RuntimeError("MkDocsOutputFormat not initialized")

        return self._posts_impl.write(
            slug=metadata["slug"],
            metadata=metadata,
            content=content
        )

    # Update write_profile similarly
    def write_profile(
        self, author_id: str, profile_data: dict[str, Any], profiles_dir: Path, **_kwargs: object
    ) -> str:
        """Write an author profile page in MkDocs format.

        Delegates to ProfileStorage implementation.
        """
        if not self._profiles_impl:
            raise RuntimeError("MkDocsOutputFormat not initialized")

        if isinstance(profile_data, str):
            content = profile_data
        elif "content" in profile_data:
            content = profile_data["content"]
        else:
            name = profile_data.get("name", author_id)
            bio = profile_data.get("bio", "")
            content = f"# {name}\n\n{bio}"

        return self._profiles_impl.write(author_id, content)
```

### Phase 3: Add Validations to MkDocsPostStorage

**File**: `src/egregora/storage/mkdocs.py`

Add the missing validation logic to `MkDocsPostStorage.write()`:

```python
import datetime
import re
from egregora.utils import slugify, safe_path_join

class MkDocsPostStorage:
    """Filesystem-based post storage following MkDocs conventions.

    Handles:
    - Slug normalization (URL safety)
    - Unique filename generation (prevents overwrites)
    - Date prefix extraction (file organization)
    - YAML frontmatter serialization
    """

    def __init__(self, site_root: Path):
        self.site_root = site_root
        self.posts_dir = site_root / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Write post to filesystem with validation.

        Args:
            slug: URL-friendly slug (will be normalized)
            metadata: YAML frontmatter dict (must include 'date')
            content: Markdown content (body only)

        Returns:
            Relative path string (e.g., "posts/2025-01-10-my-post.md")

        Raises:
            ValueError: If required metadata is missing
        """
        import yaml

        # 1. Normalize slug for URL/filesystem safety
        normalized_slug = slugify(slug)

        # 2. Extract date prefix for organization
        date_prefix = self._extract_clean_date(metadata.get("date", ""))

        # 3. Generate unique filename (prevent overwrites)
        base_filename = f"{date_prefix}-{normalized_slug}.md"
        filepath = safe_path_join(self.posts_dir, base_filename)

        # If file exists, add suffix to make unique
        suffix = 2
        while filepath.exists():
            filename = f"{date_prefix}-{normalized_slug}-{suffix}.md"
            filepath = safe_path_join(self.posts_dir, filename)
            suffix += 1

        # 4. Update metadata with normalized slug
        metadata_copy = metadata.copy()
        metadata_copy["slug"] = normalized_slug

        # 5. Write with YAML frontmatter
        frontmatter = yaml.dump(metadata_copy, sort_keys=False, allow_unicode=True)
        full_content = f"---\n{frontmatter}---\n\n{content}"
        filepath.write_text(full_content, encoding="utf-8")

        return str(filepath.relative_to(self.site_root))

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Read post from filesystem.

        Searches for post by normalized slug, handling date prefixes.
        """
        # Normalize slug for searching
        normalized = slugify(slug)

        # Search for any file matching slug pattern (handles date prefixes)
        for path in self.posts_dir.glob(f"*{normalized}.md"):
            raw_content = path.read_text(encoding="utf-8")
            return self._parse_frontmatter(raw_content)

        # Also try exact slug match (for backward compatibility)
        exact_path = self.posts_dir / f"{slug}.md"
        if exact_path.exists():
            raw_content = exact_path.read_text(encoding="utf-8")
            return self._parse_frontmatter(raw_content)

        return None

    def exists(self, slug: str) -> bool:
        """Check if post exists.

        Searches by normalized slug pattern to handle date prefixes.
        """
        normalized = slugify(slug)

        # Check for any file matching the slug
        if any(self.posts_dir.glob(f"*{normalized}.md")):
            return True

        # Also check exact match
        return (self.posts_dir / f"{slug}.md").exists()

    @staticmethod
    def _extract_clean_date(date_str: str) -> str:
        """Extract clean YYYY-MM-DD date from various formats.

        Handles:
        - Clean dates: "2025-03-02"
        - ISO timestamps: "2025-03-02T10:30:00"
        - Window labels: "2025-03-02 08:01 to 12:49"
        - Datetimes: "2025-03-02 10:30:45"

        Args:
            date_str: Date string in various formats

        Returns:
            Clean date in YYYY-MM-DD format, or today's date if parsing fails
        """
        if not date_str:
            return datetime.date.today().isoformat()

        date_str = date_str.strip()

        # Try ISO date first (YYYY-MM-DD)
        if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
            try:
                datetime.date.fromisoformat(date_str)
                return date_str
            except (ValueError, AttributeError):
                pass

        # Extract YYYY-MM-DD pattern from longer strings
        match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        if match:
            clean_date = match.group(1)
            try:
                datetime.date.fromisoformat(clean_date)
                return clean_date
            except (ValueError, AttributeError):
                pass

        # Fallback: use today's date
        return datetime.date.today().isoformat()

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: Raw markdown with frontmatter

        Returns:
            (metadata dict, body string)

        Raises:
            ValueError: If frontmatter is malformed
        """
        import yaml

        if not content.startswith("---\n"):
            return {}, content

        # Find end of frontmatter
        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            return {}, content

        # Extract and parse frontmatter
        frontmatter_text = content[4:end_marker]
        body = content[end_marker + 5:].lstrip()

        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}") from e

        return metadata, body
```

### Phase 4: Update Writer Agent to Use OutputFormat

**File**: `src/egregora/agents/writer/core.py`

Replace the `_create_storage_implementations()` factory with OutputFormat usage:

```python
# REMOVE this function:
# def _create_storage_implementations(site_root: Path) -> tuple[PostStorage, ProfileStorage, JournalStorage]:
#     from egregora.storage.mkdocs import MkDocsJournalStorage, MkDocsPostStorage, MkDocsProfileStorage
#     return (
#         MkDocsPostStorage(site_root),
#         MkDocsProfileStorage(site_root),
#         MkDocsJournalStorage(site_root),
#     )

# ADD this instead:
def _create_output_format(site_root: Path) -> OutputFormat:
    """Create and initialize output format for the site.

    Auto-detects format (MkDocs vs Hugo) or defaults to MkDocs.

    Args:
        site_root: Root directory of the site

    Returns:
        Initialized OutputFormat instance providing storage protocols
    """
    from egregora.rendering import output_registry

    # Try to auto-detect format
    output_format = output_registry.detect_format(site_root)

    # Default to MkDocs if no detection
    if output_format is None:
        output_format = output_registry.get_format("mkdocs")

    # Initialize storage implementations
    output_format.initialize(site_root)

    return output_format
```

Update the calling code:

```python
# Instead of:
# posts, profiles, journals = _create_storage_implementations(site_root)

# Use:
output_format = _create_output_format(site_root)

context = WriterRuntimeContext(
    posts=output_format.posts,
    profiles=output_format.profiles,
    journals=output_format.journals,
    # ... rest of context
)
```

### Phase 5: Update HugoOutputFormat Similarly

**File**: `src/egregora/rendering/hugo.py`

Add the same storage protocol properties to `HugoOutputFormat`:

```python
class HugoOutputFormat(OutputFormat):
    """Hugo output format implementation."""

    def __init__(self):
        self._site_root: Path | None = None
        self._posts_impl: PostStorage | None = None
        self._profiles_impl: ProfileStorage | None = None
        self._journals_impl: JournalStorage | None = None
        self._enrichments_impl: EnrichmentStorage | None = None

    def initialize(self, site_root: Path) -> None:
        """Initialize Hugo storage implementations."""
        self._site_root = site_root

        # TODO: Create Hugo-specific storage implementations
        # For now, can reuse MkDocs implementations or create Hugo variants
        from egregora.storage.mkdocs import (
            MkDocsPostStorage,
            MkDocsProfileStorage,
            MkDocsJournalStorage,
            MkDocsEnrichmentStorage
        )

        self._posts_impl = MkDocsPostStorage(site_root)
        self._profiles_impl = MkDocsProfileStorage(site_root)
        self._journals_impl = MkDocsJournalStorage(site_root)
        self._enrichments_impl = MkDocsEnrichmentStorage(site_root)

    @property
    def posts(self) -> PostStorage:
        if self._posts_impl is None:
            raise RuntimeError("HugoOutputFormat not initialized")
        return self._posts_impl

    # ... same pattern for profiles, journals, enrichments ...
```

### Phase 6: Add Comprehensive Tests

**File**: `tests/storage/test_mkdocs_post_storage.py` (new file)

```python
"""Tests for MkDocsPostStorage validation logic."""

import pytest
from pathlib import Path

from egregora.storage.mkdocs import MkDocsPostStorage


def test_post_storage_normalizes_slugs(tmp_path: Path):
    """PostStorage must sanitize slugs to be URL-safe."""
    storage = MkDocsPostStorage(tmp_path)

    # Slug with special characters
    result = storage.write(
        slug="My Post!@# With Spaces",
        metadata={"title": "Test", "date": "2025-01-10"},
        content="Content"
    )

    # Should normalize to valid filename
    assert "my-post" in result.lower()
    assert "!@#" not in result
    assert " " not in result


def test_post_storage_generates_unique_filenames(tmp_path: Path):
    """PostStorage must not overwrite existing posts."""
    storage = MkDocsPostStorage(tmp_path)

    # Write first post
    id1 = storage.write(
        slug="test-post",
        metadata={"title": "Post 1", "date": "2025-01-10"},
        content="Content 1"
    )

    # Write second post with same slug
    id2 = storage.write(
        slug="test-post",
        metadata={"title": "Post 2", "date": "2025-01-10"},
        content="Content 2"
    )

    # Should generate different filenames
    assert id1 != id2
    assert "test-post" in id1
    assert "test-post" in id2

    # Both files should exist
    assert (tmp_path / id1).exists()
    assert (tmp_path / id2).exists()

    # Second file should have suffix
    assert "-2" in id2 or id2.endswith("test-post-2.md")


def test_post_storage_adds_date_prefix(tmp_path: Path):
    """PostStorage must add date prefix to filenames."""
    storage = MkDocsPostStorage(tmp_path)

    result = storage.write(
        slug="my-post",
        metadata={"title": "Test", "date": "2025-03-15"},
        content="Content"
    )

    # Should have date prefix
    assert "2025-03-15" in result
    assert result.startswith("posts/2025-03-15-")


def test_post_storage_handles_window_labels(tmp_path: Path):
    """PostStorage must extract date from window labels."""
    storage = MkDocsPostStorage(tmp_path)

    # Window label format
    result = storage.write(
        slug="my-post",
        metadata={"title": "Test", "date": "2025-03-15 10:00 to 12:00"},
        content="Content"
    )

    # Should extract clean date
    assert "2025-03-15" in result


def test_post_storage_read_finds_by_slug(tmp_path: Path):
    """PostStorage.read() must find posts by normalized slug."""
    storage = MkDocsPostStorage(tmp_path)

    # Write with date prefix
    storage.write(
        slug="my-post",
        metadata={"title": "Test Post", "date": "2025-01-10"},
        content="Test content"
    )

    # Read by slug (without date prefix)
    result = storage.read("my-post")

    assert result is not None
    metadata, content = result
    assert metadata["title"] == "Test Post"
    assert content == "Test content"


def test_post_storage_exists_checks_by_slug(tmp_path: Path):
    """PostStorage.exists() must check by normalized slug."""
    storage = MkDocsPostStorage(tmp_path)

    # Before write
    assert not storage.exists("test-post")

    # Write with date prefix
    storage.write(
        slug="test-post",
        metadata={"title": "Test", "date": "2025-01-10"},
        content="Content"
    )

    # Should find by slug (without date prefix)
    assert storage.exists("test-post")


def test_post_storage_roundtrip_with_frontmatter(tmp_path: Path):
    """PostStorage must preserve metadata through write-read cycle."""
    storage = MkDocsPostStorage(tmp_path)

    original_metadata = {
        "title": "Test Post",
        "date": "2025-01-10",
        "tags": ["python", "testing"],
        "authors": ["uuid-123"],
        "summary": "A test post",
    }
    original_content = "# Heading\n\nTest content here."

    # Write
    storage.write(
        slug="test-post",
        metadata=original_metadata,
        content=original_content
    )

    # Read
    result = storage.read("test-post")
    assert result is not None

    metadata, content = result

    # Verify metadata preserved
    assert metadata["title"] == "Test Post"
    assert metadata["tags"] == ["python", "testing"]
    assert metadata["authors"] == ["uuid-123"]

    # Verify content preserved
    assert content == original_content
```

**File**: `tests/rendering/test_mkdocs_output_format.py`

```python
"""Tests for MkDocsOutputFormat integration with storage protocols."""

import pytest
from pathlib import Path

from egregora.rendering.mkdocs import MkDocsOutputFormat


def test_output_format_requires_initialization(tmp_path: Path):
    """OutputFormat properties must raise error before initialization."""
    output_format = MkDocsOutputFormat()

    with pytest.raises(RuntimeError, match="not initialized"):
        _ = output_format.posts

    with pytest.raises(RuntimeError, match="not initialized"):
        _ = output_format.profiles


def test_output_format_provides_storage_protocols(tmp_path: Path):
    """Initialized OutputFormat must provide storage protocol implementations."""
    output_format = MkDocsOutputFormat()
    output_format.initialize(tmp_path)

    # Should provide all storage protocols
    assert output_format.posts is not None
    assert output_format.profiles is not None
    assert output_format.journals is not None
    assert output_format.enrichments is not None

    # Should satisfy protocol types
    from egregora.storage import PostStorage, ProfileStorage, JournalStorage, EnrichmentStorage
    assert isinstance(output_format.posts, PostStorage)
    assert isinstance(output_format.profiles, ProfileStorage)
    assert isinstance(output_format.journals, JournalStorage)
    assert isinstance(output_format.enrichments, EnrichmentStorage)


def test_output_format_write_post_delegates_to_storage(tmp_path: Path):
    """OutputFormat.write_post() must delegate to PostStorage."""
    output_format = MkDocsOutputFormat()
    output_format.initialize(tmp_path)

    metadata = {"slug": "test-post", "title": "Test", "date": "2025-01-10"}
    content = "Test content"

    # Call OutputFormat method
    result = output_format.write_post(content, metadata, tmp_path / "posts")

    # Should create file via storage
    assert result is not None
    assert (tmp_path / result).exists()

    # Should be accessible via storage protocol
    assert output_format.posts.exists("test-post")
```

### Phase 7: Update Documentation

**File**: `REFACTOR_ADAPTER_PATTERN.md`

Update the status section to reflect the fix:

```markdown
## ✅ IMPLEMENTATION COMPLETE + FIXES APPLIED (2025-11-10)

All phases of the adapter pattern refactoring have been successfully implemented:

- ✅ **Phase 1-6**: Storage protocols and agent integration complete
- ✅ **Fix 1**: Storage protocols now provided through OutputFormat coordinator
- ✅ **Fix 2**: Data integrity validations added to MkDocsPostStorage
  - Slug normalization with `slugify()`
  - Unique filename generation (prevents overwrites)
  - Date prefix extraction (file organization)

**Architecture**:
- OutputFormat (MkDocs/Hugo) provides storage protocol implementations
- Storage protocols handle format-specific logic (validation, file naming)
- Writer agent receives storage through OutputFormat coordinator
```

**File**: `CLAUDE.md`

Add a section on OutputFormat usage:

```markdown
## Output Format Architecture

Egregora uses the **OutputFormat** pattern to coordinate all storage operations:

```python
from egregora.rendering import output_registry

# Auto-detect format (MkDocs, Hugo, etc.)
output_format = output_registry.detect_format(site_root)
output_format.initialize(site_root)

# Get storage implementations
context = WriterRuntimeContext(
    posts=output_format.posts,
    profiles=output_format.profiles,
    journals=output_format.journals,
    enrichments=output_format.enrichments,
    ...
)
```

**Adding new output formats**:

1. Implement `OutputFormat` abstract class
2. Provide storage protocol implementations
3. Register with `output_registry.register(YourFormat)`
4. Auto-detection works automatically
```

---

## Testing Checklist

Before merging, verify:

- [ ] All existing tests pass
- [ ] New storage validation tests pass (slug normalization, unique filenames, date prefix)
- [ ] OutputFormat integration tests pass
- [ ] Writer agent works with OutputFormat-provided storage
- [ ] Hugo output format still works (even if reusing MkDocs storage temporarily)
- [ ] Registry auto-detection works for MkDocs sites
- [ ] No regression in post/profile/journal writing

---

## Migration Path

### For External Consumers (if any)

If any external code was using the storage protocols directly:

```python
# OLD (direct usage)
from egregora.storage.mkdocs import MkDocsPostStorage
posts = MkDocsPostStorage(site_root)

# NEW (through OutputFormat)
from egregora.rendering import output_registry
output_format = output_registry.get_format("mkdocs")
output_format.initialize(site_root)
posts = output_format.posts
```

### Deprecation Timeline

1. **v0.X** (this PR): OutputFormat provides storage, old direct usage still works
2. **v0.X+1**: Add deprecation warnings to direct storage imports
3. **v0.X+2**: Remove ability to import storage implementations directly

---

## Benefits After Fix

✅ **Single coordinator** - OutputFormat manages all format-specific operations
✅ **Easy to extend** - Adding DatabaseOutputFormat or S3OutputFormat is straightforward
✅ **Data integrity** - Slug normalization and unique filenames prevent corruption
✅ **Uses existing abstraction** - OutputFormat registry pattern fully utilized
✅ **Auto-detection** - Sites auto-detected as MkDocs/Hugo/etc.
✅ **Type safety** - Storage protocols maintain strong typing
✅ **Clean separation** - Format coordination separate from storage implementation

---

## Estimated Implementation Time

- Phase 1-2 (OutputFormat properties): **1 hour**
- Phase 3 (MkDocs validation logic): **1.5 hours**
- Phase 4 (Update writer agent): **30 minutes**
- Phase 5 (Update Hugo): **30 minutes**
- Phase 6 (Tests): **1.5 hours**
- Phase 7 (Documentation): **30 minutes**

**Total**: ~6 hours

---

## Questions?

If anything is unclear or needs more detail, please ask. This document aims to provide a complete implementation guide that can be followed step-by-step.
