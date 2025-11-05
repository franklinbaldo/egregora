# Code Smells Analysis & Refactoring Guide

**Generated**: 2025-11-05
**Codebase**: Egregora
**Analysis Tool**: Python AST + Pattern Matching

---

## Executive Summary

This document catalogs code smells found in the Egregora codebase and provides concrete refactoring strategies. The analysis identified **7 high-priority issues**, **8 medium-priority issues**, and **5 low-priority maintenance items**.

### Quick Stats

| Category | Count | Severity | Est. Effort |
|----------|-------|----------|-------------|
| Bare `except Exception:` clauses | 7 | 🔴 High | 2 hours |
| God functions (100+ lines) | 1 (391 lines!) | 🔴 High | 8 hours |
| Long parameter lists (10+ params) | 6 | 🔴 High | 4 hours |
| Deep nesting (4+ levels) | 2+ | 🟡 Medium | 3 hours |
| Flag arguments | 4+ | 🟡 Medium | 2 hours |
| Magic strings/numbers | 20+ | 🟢 Low | 1 hour |
| Utils organization | 1 directory | 🟡 Medium | 3 hours |

**Total estimated effort**: ~23 hours

---

## 1. Bare Exception Handlers 🔴 High Priority

### Problem

Catching `Exception` without specific handling masks bugs and makes debugging difficult. These broad catches can hide programming errors, typos, and unexpected failures.

### Findings (7 instances)

#### 1.1 Database Schema Operations
**File**: `src/egregora/database/schema.py`

**Line 233** - `add_primary_key()`
```python
except Exception:
    # Constraint may already exist
    pass
```

**Line 261** - `ensure_identity_column()`
```python
except Exception:
    # Identity already configured or column contains incompatible data
    pass
```

**Impact**: Hides all database errors including connection issues, permission problems, and SQL syntax errors.

#### 1.2 File Operations
**File**: `src/egregora/enrichment/core.py`

**Line 77-83** - `_atomic_write_text()`
```python
except Exception:
    # Clean up temp file on error
    try:
        os.unlink(temp_path)
    except OSError:
        pass
    raise
```

**Line 470** - `enrich_table()`
```python
except Exception as delete_error:
    logger.error("Failed to delete %s: %s", media_job.file_path, delete_error)
```

**Impact**: Catches all exceptions when only file-related errors are expected.

#### 1.3 Type Handling
**File**: `src/egregora/cli.py`

**Line 84** - `_make_json_safe()`
```python
except Exception:  # pragma: no cover - fallback to string or error
    pass
```

**Impact**: Silently converts all errors to strings, hiding type conversion bugs.

#### 1.4 Test Infrastructure
**File**: `tests/conftest.py`

**Line 45**
```python
except Exception:  # pragma: no cover - runtime safety for optional dependency
    _real_sdk_available = False
```

**Impact**: Less critical (test setup), but still too broad.

#### 1.5 Internal Tool Operations
**File**: `src/egregora/agents/tools/rag/store.py`

**Line 921** - `_ensure_local_table()`
```python
except Exception:  # pragma: no cover - defensive against Ibis internals
    backend = None
```

**Impact**: Hides Ibis library errors that might need proper handling.

### Proposed Solutions

#### Template for Database Operations
```python
# Instead of:
try:
    conn.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({column_name})")
except Exception:
    pass

# Use:
from duckdb import ConstraintException, CatalogException

try:
    conn.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({column_name})")
except ConstraintException:
    logger.debug("Primary key already exists on %s.%s", table_name, column_name)
except CatalogException as e:
    logger.warning("Table or column not found: %s", e)
```

#### Template for File Operations
```python
# Instead of:
try:
    os.unlink(temp_path)
except Exception:
    pass

# Use:
try:
    os.unlink(temp_path)
except (FileNotFoundError, PermissionError) as e:
    logger.debug("Could not clean up temp file %s: %s", temp_path, e)
except OSError as e:
    logger.warning("Unexpected OS error cleaning %s: %s", temp_path, e)
```

#### Template for Type Conversions
```python
# Instead of:
try:
    return complex_type_conversion(value)
except Exception:
    pass

# Use:
try:
    return complex_type_conversion(value)
except (TypeError, ValueError, AttributeError) as e:
    logger.debug("Type conversion failed for %r: %s", value, e)
    return str(value)
```

### Implementation Checklist

- [ ] `database/schema.py:233` - Use `ConstraintException`
- [ ] `database/schema.py:261` - Use `ConstraintException`, `CatalogException`
- [ ] `enrichment/core.py:77` - Use `(IOError, OSError)`
- [ ] `enrichment/core.py:470` - Use `(FileNotFoundError, PermissionError, OSError)`
- [ ] `cli.py:84` - Use `(TypeError, ValueError, AttributeError)`
- [ ] `tests/conftest.py:45` - Use `(ImportError, AttributeError)`
- [ ] `agents/tools/rag/store.py:921` - Research specific Ibis exceptions

---

## 2. God Function: `enrich_table()` 🔴 High Priority

### Problem

**File**: `src/egregora/enrichment/core.py:92-482`
**Lines**: 391 (!!!)

This single function violates the Single Responsibility Principle by doing:
1. URL extraction and enrichment
2. Media reference enrichment
3. Batch processing coordination
4. Cache key generation and lookup
5. Progress tracking with logging
6. Table mutations and column management
7. Retry logic and error handling
8. Job queue management

### Current Structure Analysis

```python
def enrich_table(
    messages_table: Table,
    # ... 13 parameters total
) -> Table:
    # Lines 92-117: Setup and validation (25 lines)
    # Lines 118-139: Initialize tracking structures (21 lines)
    # Lines 140-237: URL enrichment loop (97 lines, deeply nested!)
    # Lines 238-312: Media enrichment loop (74 lines)
    # Lines 313-389: Batch processing logic (76 lines)
    # Lines 390-460: Apply enrichments to table (70 lines)
    # Lines 461-482: Media file cleanup (21 lines)
```

### Proposed Refactoring

#### Strategy Pattern for Enrichment Types

```python
# enrichment/strategies.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

@dataclass
class EnrichmentJob:
    """Single enrichment task."""
    message_id: int
    content_type: str  # "url" or "media"
    source: str  # URL or media reference
    context: str  # Original message text
    cache_key: str

@dataclass
class EnrichmentResult:
    """Result of enrichment operation."""
    job: EnrichmentJob
    enriched_text: str
    success: bool
    error: str | None = None

class EnrichmentStrategy(Protocol):
    """Interface for enrichment strategies."""

    def extract_jobs(
        self,
        table: Table,
        seen_keys: set[str],
        max_jobs: int
    ) -> list[EnrichmentJob]:
        """Extract enrichment jobs from table."""
        ...

    def enrich_batch(
        self,
        jobs: list[EnrichmentJob],
        cache: dict[str, str]
    ) -> list[EnrichmentResult]:
        """Process a batch of jobs."""
        ...

# enrichment/url_enrichment.py
class URLEnrichmentStrategy:
    """Enriches URLs found in messages."""

    def __init__(self, gemini_client, model: str, cache_dir: Path):
        self.client = gemini_client
        self.model = model
        self.cache = URLEnrichmentCache(cache_dir)

    def extract_jobs(
        self,
        table: Table,
        seen_keys: set[str],
        max_jobs: int
    ) -> list[EnrichmentJob]:
        """Extract URLs from messages and create jobs."""
        jobs = []
        for row in table.execute():
            if len(jobs) >= max_jobs:
                break

            urls = extract_urls(row.message or "")
            for url in urls[:3]:  # Max 3 URLs per message
                cache_key = make_enrichment_cache_key(
                    content_type="url",
                    source=url,
                    model=self.model
                )

                if cache_key in seen_keys:
                    continue

                jobs.append(EnrichmentJob(
                    message_id=row.id,
                    content_type="url",
                    source=url,
                    context=row.message,
                    cache_key=cache_key
                ))
                seen_keys.add(cache_key)

        return jobs

    def enrich_batch(
        self,
        jobs: list[EnrichmentJob],
        cache: dict[str, str]
    ) -> list[EnrichmentResult]:
        """Batch process URL enrichments."""
        # Check cache first
        results = []
        uncached_jobs = []

        for job in jobs:
            if cached := cache.get(job.cache_key):
                results.append(EnrichmentResult(
                    job=job,
                    enriched_text=cached,
                    success=True
                ))
            else:
                uncached_jobs.append(job)

        # Batch process uncached
        if uncached_jobs:
            batch_results = self._batch_enrich_urls(uncached_jobs)
            results.extend(batch_results)

            # Update cache
            for result in batch_results:
                if result.success:
                    cache[result.job.cache_key] = result.enriched_text

        return results

    def _batch_enrich_urls(self, jobs: list[EnrichmentJob]) -> list[EnrichmentResult]:
        """Call Gemini API for batch URL enrichment."""
        # Implementation here...
        pass

# enrichment/media_enrichment.py
class MediaEnrichmentStrategy:
    """Enriches media references with vision model."""

    def __init__(
        self,
        gemini_client,
        model: str,
        media_dir: Path,
        cache_dir: Path
    ):
        self.client = gemini_client
        self.model = model
        self.media_dir = media_dir
        self.cache = MediaEnrichmentCache(cache_dir)

    def extract_jobs(
        self,
        table: Table,
        seen_keys: set[str],
        max_jobs: int
    ) -> list[EnrichmentJob]:
        """Extract media references and create jobs."""
        # Similar structure to URL extraction
        pass

    def enrich_batch(
        self,
        jobs: list[EnrichmentJob],
        cache: dict[str, str]
    ) -> list[EnrichmentResult]:
        """Batch process media enrichments."""
        # Similar structure to URL batch processing
        pass
```

#### Coordinator Function

```python
# enrichment/coordinator.py
from dataclasses import dataclass

@dataclass
class EnrichmentConfig:
    """Configuration for enrichment pipeline."""
    max_enrichments: int = 500
    batch_threshold: int = 10
    enable_url: bool = True
    enable_media: bool = True
    gemini_api_key: str | None = None
    model: str = "models/gemini-flash-latest"
    vision_model: str = "models/gemini-flash-latest"

class EnrichmentCoordinator:
    """Coordinates multiple enrichment strategies."""

    def __init__(
        self,
        strategies: list[EnrichmentStrategy],
        config: EnrichmentConfig
    ):
        self.strategies = strategies
        self.config = config

    def enrich_table(self, table: Table) -> Table:
        """
        Main enrichment pipeline coordinator.

        Replaces the 391-line god function with clean orchestration.
        """
        if table.count().execute() == 0:
            return table

        # Collect all jobs from all strategies
        all_jobs = self._collect_jobs(table)

        # Process in batches
        all_results = self._process_batches(all_jobs)

        # Apply results to table
        enriched_table = self._apply_results(table, all_results)

        # Cleanup temporary files
        self._cleanup_temp_files(all_results)

        return enriched_table

    def _collect_jobs(self, table: Table) -> list[EnrichmentJob]:
        """Collect jobs from all strategies."""
        seen_keys = set()
        all_jobs = []

        for strategy in self.strategies:
            remaining = self.config.max_enrichments - len(all_jobs)
            if remaining <= 0:
                break

            jobs = strategy.extract_jobs(table, seen_keys, remaining)
            all_jobs.extend(jobs)

        logger.info("Collected %d enrichment jobs", len(all_jobs))
        return all_jobs

    def _process_batches(
        self,
        jobs: list[EnrichmentJob]
    ) -> list[EnrichmentResult]:
        """Process jobs in batches with progress tracking."""
        results = []

        # Group jobs by strategy type
        jobs_by_type = self._group_jobs_by_type(jobs)

        for content_type, type_jobs in jobs_by_type.items():
            strategy = self._get_strategy_for_type(content_type)

            # Process in batches
            for i in range(0, len(type_jobs), self.config.batch_threshold):
                batch = type_jobs[i:i + self.config.batch_threshold]

                logger.info(
                    "Processing %s batch %d/%d (%d items)",
                    content_type,
                    i // self.config.batch_threshold + 1,
                    (len(type_jobs) + self.config.batch_threshold - 1)
                        // self.config.batch_threshold,
                    len(batch)
                )

                batch_results = strategy.enrich_batch(batch, {})
                results.extend(batch_results)

        return results

    def _apply_results(
        self,
        table: Table,
        results: list[EnrichmentResult]
    ) -> Table:
        """Apply enrichment results to table."""
        # Group results by message_id
        enrichments_by_message = {}
        for result in results:
            if not result.success:
                continue

            msg_id = result.job.message_id
            if msg_id not in enrichments_by_message:
                enrichments_by_message[msg_id] = []
            enrichments_by_message[msg_id].append(result.enriched_text)

        # Apply to table
        return apply_enrichments_to_table(table, enrichments_by_message)

    def _cleanup_temp_files(self, results: list[EnrichmentResult]) -> None:
        """Clean up any temporary media files."""
        for result in results:
            if result.job.content_type == "media":
                self._try_delete_media_file(result.job.source)

    def _try_delete_media_file(self, filepath: str) -> None:
        """Safely attempt to delete media file."""
        try:
            Path(filepath).unlink()
        except (FileNotFoundError, PermissionError) as e:
            logger.debug("Could not delete %s: %s", filepath, e)
        except OSError as e:
            logger.warning("Unexpected error deleting %s: %s", filepath, e)
```

#### New Entry Point

```python
# enrichment/core.py (refactored)
def enrich_table(
    messages_table: Table,
    config: EnrichmentConfig,
    gemini_client=None,
    cache_dir: Path | None = None,
    media_dir: Path | None = None,
) -> Table:
    """
    Enrich messages with URL summaries and media descriptions.

    This is now a thin wrapper that sets up strategies and delegates
    to the coordinator. Down from 391 lines to ~30 lines!

    Args:
        messages_table: Table with message data
        config: Enrichment configuration
        gemini_client: Optional pre-configured Gemini client
        cache_dir: Directory for enrichment cache
        media_dir: Directory containing media files

    Returns:
        Table with enrichment columns added
    """
    strategies = []

    if config.enable_url:
        strategies.append(URLEnrichmentStrategy(
            gemini_client=gemini_client,
            model=config.model,
            cache_dir=cache_dir
        ))

    if config.enable_media and media_dir:
        strategies.append(MediaEnrichmentStrategy(
            gemini_client=gemini_client,
            model=config.vision_model,
            media_dir=media_dir,
            cache_dir=cache_dir
        ))

    coordinator = EnrichmentCoordinator(strategies, config)
    return coordinator.enrich_table(messages_table)
```

### Benefits of Refactoring

1. **Testability**: Each strategy can be tested independently
2. **Maintainability**: Clear separation of concerns
3. **Extensibility**: Easy to add new enrichment types (e.g., link previews, PDF extraction)
4. **Readability**: Each function < 50 lines
5. **Reusability**: Strategies can be used outside the main pipeline

### Migration Path

1. Create new files alongside existing code
2. Add feature flag: `use_legacy_enrichment = True`
3. Run both implementations in parallel, compare results
4. Switch flag once validated
5. Remove old implementation

---

## 3. Long Parameter Lists 🔴 High Priority

### Problem

Functions with 10+ parameters are hard to call, test, and maintain. They often indicate missing abstractions.

### Top Offenders

| File | Function | Params | Suppressed Lint |
|------|----------|--------|-----------------|
| `pipeline.py:146` | `_process_whatsapp_export` | 16 | ✅ Yes (`PLR0913`) |
| `pipeline.py:455` | `process_whatsapp_export` | 15 | ❌ No |
| `agents/writer/core.py:182` | `_process_tool_calls` | 14 | ❌ No |
| `enrichment/core.py:92` | `enrich_table` | 13 | ❌ No |
| `cli.py:268` | `process` | 13 | ❌ No |
| `agents/tools/rag/retriever.py:477` | `query_media` | 12 | ❌ No |

### Proposed Solutions

#### 3.1 Pipeline Configuration

**Before** (`pipeline.py:146`):
```python
def _process_whatsapp_export(  # noqa: PLR0913
    zip_path: Path,
    output_dir: Path,
    *,
    site_paths: SitePaths,
    period: str = "day",
    enable_enrichment: bool = True,
    from_date=None,
    to_date=None,
    timezone=None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
```

**After**:
```python
# config/pipeline.py
from dataclasses import dataclass
from datetime import date

@dataclass
class TimeRangeConfig:
    """Configuration for date filtering."""
    period: str = "day"  # "day" | "week" | "month"
    from_date: date | None = None
    to_date: date | None = None
    timezone: str = "UTC"

@dataclass
class EnrichmentConfig:
    """Configuration for enrichment step."""
    enabled: bool = True
    model: str = "models/gemini-flash-latest"
    batch_threshold: int = 10
    max_enrichments: int = 500

@dataclass
class RetrievalConfig:
    """Configuration for RAG retrieval."""
    mode: str = "ann"  # "ann" | "flat"
    nprobe: int | None = None
    overfetch: int | None = None

@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    time_range: TimeRangeConfig
    enrichment: EnrichmentConfig
    retrieval: RetrievalConfig
    resume: bool = True

    @classmethod
    def from_cli_args(cls, **kwargs) -> "PipelineConfig":
        """Create config from CLI arguments."""
        return cls(
            time_range=TimeRangeConfig(
                period=kwargs.get("period", "day"),
                from_date=kwargs.get("from_date"),
                to_date=kwargs.get("to_date"),
                timezone=kwargs.get("timezone", "UTC")
            ),
            enrichment=EnrichmentConfig(
                enabled=kwargs.get("enable_enrichment", True),
                model=kwargs.get("model", "models/gemini-flash-latest"),
                batch_threshold=kwargs.get("batch_threshold", 10)
            ),
            retrieval=RetrievalConfig(
                mode=kwargs.get("retrieval_mode", "ann"),
                nprobe=kwargs.get("retrieval_nprobe"),
                overfetch=kwargs.get("retrieval_overfetch")
            ),
            resume=kwargs.get("resume", True)
        )

# pipeline.py (refactored)
def _process_whatsapp_export(
    zip_path: Path,
    output_dir: Path,
    site_paths: SitePaths,
    config: PipelineConfig,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """
    Complete pipeline: ZIP → posts + profiles.

    Down from 16 parameters to 5!
    """
    # Implementation uses config.time_range.period, etc.
```

#### 3.2 Tool Call Processing

**Before** (`agents/writer/core.py:182`):
```python
def _process_tool_calls(
    tool_calls: list,
    tools: dict,
    con,
    messages_table,
    profiles_table,
    site_config: dict,
    profiles_dir: Path,
    rag_chunk_table,
    rag_meta_table,
    gemini_client,
    model: str,
    site_paths: SitePaths,
    site_path: Path,
    writer_vars: dict[str, Any],
) -> tuple[list[dict], str]:
```

**After**:
```python
# agents/writer/context.py
@dataclass
class WriterContext:
    """Complete context for writer agent operations."""
    # Database tables
    con: Any
    messages_table: Table
    profiles_table: Table
    rag_chunk_table: Table
    rag_meta_table: Table

    # Configuration
    site_config: dict[str, Any]
    site_paths: SitePaths
    site_path: Path
    profiles_dir: Path

    # LLM client
    gemini_client: Any
    model: str

    # Variables
    writer_vars: dict[str, Any]

    @classmethod
    def from_session(cls, session: "WriterSession") -> "WriterContext":
        """Create context from active session."""
        return cls(
            con=session.con,
            messages_table=session.messages_table,
            profiles_table=session.profiles_table,
            rag_chunk_table=session.rag_chunk_table,
            rag_meta_table=session.rag_meta_table,
            site_config=session.site_config,
            site_paths=session.site_paths,
            site_path=session.site_path,
            profiles_dir=session.profiles_dir,
            gemini_client=session.gemini_client,
            model=session.model,
            writer_vars=session.writer_vars
        )

# agents/writer/core.py (refactored)
def _process_tool_calls(
    tool_calls: list,
    tools: dict,
    context: WriterContext,
) -> tuple[list[dict], str]:
    """
    Process tool calls from agent.

    Down from 14 parameters to 3!
    """
    # Implementation uses context.con, context.messages_table, etc.
```

### Implementation Checklist

- [ ] Create `config/pipeline.py` with config dataclasses
- [ ] Create `agents/writer/context.py` with `WriterContext`
- [ ] Refactor `_process_whatsapp_export` to use `PipelineConfig`
- [ ] Refactor `_process_tool_calls` to use `WriterContext`
- [ ] Update CLI commands to build configs
- [ ] Update tests to use new configs

---

## 4. Deep Nesting 🟡 Medium Priority

### Problem

Code with 4+ indentation levels is hard to follow and indicates missing abstractions.

### Finding 4.1: Enrichment Loops

**File**: `src/egregora/enrichment/core.py:140-237`

```python
for row in rows:                                    # Level 1
    if enrichment_count >= max_enrichments:        # Level 2
        break

    if enable_url and message:                      # Level 2
        urls = extract_urls(message)
        for url in urls[:3]:                        # Level 3
            if enrichment_count >= max_enrichments: # Level 4
                break
            cache_key = make_enrichment_cache_key(...)
            if cache_key in seen_url_keys:          # Level 4
                continue
            # ... more Level 4 code

    if enable_media and media_filename_lookup:     # Level 2
        media_refs = find_media_references(message)
        for ref in media_refs:                      # Level 3
            if enrichment_count >= max_enrichments: # Level 4
                break
            lookup_result = media_filename_lookup.get(ref)
            if not lookup_result:                   # Level 4
                continue
            # ... more Level 4+ code
```

**Solution**: Extract inner loops to methods

```python
def _process_row_for_urls(
    row,
    enrichment_count: int,
    max_enrichments: int,
    seen_keys: set[str],
    url_jobs: list[EnrichmentJob]
) -> int:
    """Extract and queue URL enrichment jobs from a row."""
    if enrichment_count >= max_enrichments:
        return enrichment_count

    if not (enable_url and row.message):
        return enrichment_count

    urls = extract_urls(row.message)
    for url in urls[:3]:
        if enrichment_count >= max_enrichments:
            break

        cache_key = make_enrichment_cache_key("url", url, model)
        if cache_key in seen_keys:
            continue

        url_jobs.append(EnrichmentJob(
            message_id=row.id,
            source=url,
            cache_key=cache_key
        ))
        seen_keys.add(cache_key)
        enrichment_count += 1

    return enrichment_count

# Main loop becomes:
for row in rows:
    enrichment_count = _process_row_for_urls(
        row, enrichment_count, max_enrichments,
        seen_url_keys, url_jobs
    )
    enrichment_count = _process_row_for_media(
        row, enrichment_count, max_enrichments,
        seen_media_keys, media_jobs
    )
```

### Finding 4.2: CLI Ranking Loop

**File**: `src/egregora/cli.py:640-677`

**Solution**: Extract comparison session to separate function

```python
def _run_single_comparison(
    config: RankingConfig,
    profiles_dir: Path,
    posts_table: Table,
    comparison_num: int,
    total_comparisons: int
) -> bool:
    """
    Run a single comparison.

    Returns:
        True if successful, False if should stop
    """
    console.print(f"\n[bold]Comparison {comparison_num}/{total_comparisons}[/bold]")

    # Get posts to compare
    try:
        post_a_id, post_b_id = get_posts_to_compare(posts_table)
    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
        return False

    # Select random profile
    profile_path = _select_profile(profiles_dir)

    # Run comparison
    try:
        run_comparison(
            post_a_id=post_a_id,
            post_b_id=post_b_id,
            profile_path=profile_path,
            # ... other args
        )
        return True
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if config.debug:
            raise
        return True  # Continue to next comparison

# Main loop becomes simple:
for i in range(config.comparisons):
    if not _run_single_comparison(config, profiles_dir, posts_table, i+1, config.comparisons):
        break
```

---

## 5. Magic Strings & Numbers 🟢 Low Priority

### Problem

Hardcoded strings and numbers scattered throughout code make it hard to maintain consistency and find all usages.

### Findings

```python
# src/egregora/ingestion/parser.py:99
if simple_cmd == "/egregora opt-out":  # Magic command string

# src/egregora/config/site.py:103
if plugin == "blog":  # Magic plugin name

# src/egregora/pipeline.py:341
if steps_state.get("enrichment") == "completed":  # Magic status

# src/egregora/utils/serialization.py:196
if output_path.suffix.lower() == ".parquet":  # Magic extension

# src/egregora/database/schema.py:281
if index_type == "HNSW":  # Magic index type
```

### Proposed Solution: Constants Module

```python
# egregora/constants.py
"""
Central location for all constants used throughout the application.
"""
from enum import Enum

# Commands
class EgregoraCommand(str, Enum):
    """User commands recognized by the system."""
    OPT_OUT = "/egregora opt-out"
    OPT_IN = "/egregora opt-in"
    HELP = "/egregora help"
    STATUS = "/egregora status"

# Plugins
class PluginType(str, Enum):
    """Available plugin types."""
    BLOG = "blog"
    FORUM = "forum"
    WIKI = "wiki"

# Pipeline steps
class PipelineStep(str, Enum):
    """Pipeline step names."""
    ENRICHMENT = "enrichment"
    WRITING = "writing"
    PROFILES = "profiles"
    RAG = "rag"

class StepStatus(str, Enum):
    """Pipeline step statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

# File formats
class FileFormat(str, Enum):
    """Supported file formats."""
    PARQUET = ".parquet"
    CSV = ".csv"
    JSON = ".json"
    DUCKDB = ".duckdb"

# Database
class IndexType(str, Enum):
    """Vector index types."""
    HNSW = "HNSW"
    FLAT = "FLAT"

class RetrievalMode(str, Enum):
    """RAG retrieval modes."""
    ANN = "ann"  # Approximate Nearest Neighbor
    FLAT = "flat"  # Exhaustive search

# Time periods
class TimePeriod(str, Enum):
    """Time period groupings."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

# Media types
class MediaType(str, Enum):
    """Media content types."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"

# Limits and thresholds
class Limits:
    """Numeric limits used throughout the system."""
    MAX_ENRICHMENTS_DEFAULT = 500
    BATCH_THRESHOLD_DEFAULT = 10
    MAX_URLS_PER_MESSAGE = 3
    MAX_MEDIA_PER_MESSAGE = 5
    RAG_DEFAULT_TOP_K = 10
    SINGLE_DIGIT_THRESHOLD = 10

# Usage:
from egregora.constants import EgregoraCommand, PluginType, StepStatus

if simple_cmd == EgregoraCommand.OPT_OUT:
    return {"command": "opt-out"}

if plugin == PluginType.BLOG:
    return DEFAULT_BLOG_DIR

if steps_state.get("enrichment") == StepStatus.COMPLETED:
    logger.info("Enrichment already completed")
```

### Benefits

1. **Single source of truth**: Change once, affects everywhere
2. **Type safety**: Enums prevent typos
3. **Discoverability**: IDE autocomplete shows all options
4. **Documentation**: Enums serve as living documentation

### Implementation Checklist

- [ ] Create `src/egregora/constants.py`
- [ ] Define all enums and constant classes
- [ ] Replace magic strings in `ingestion/parser.py`
- [ ] Replace magic strings in `config/site.py`
- [ ] Replace magic strings in `pipeline.py`
- [ ] Replace magic strings in `utils/serialization.py`
- [ ] Replace magic strings in `database/schema.py`
- [ ] Update tests to use constants

---

## 6. Utils Directory Organization 🟡 Medium Priority

### Problem

The `utils/` directory has become a grab-bag with 13+ modules, making it hard to find related functionality.

### Current Structure

```
src/egregora/utils/
├── base_dispatcher.py         (Dispatcher pattern base)
├── cache.py                    (Caching utilities)
├── paths.py                    (Path helpers)
├── logfire_config.py          (Logging setup)
├── batch.py                    (314 lines - Batch processing)
├── logging_setup.py           (More logging)
├── genai.py                    (233 lines - Gemini dispatch)
├── zip.py                      (ZIP utilities)
├── write_post.py              (Post writing)
├── serialization.py           (256 lines - Table I/O)
├── checkpoints.py             (Checkpoint management)
├── gemini_dispatcher.py       (269 lines - More Gemini)
└── [more files...]
```

### Proposed Reorganization

Organize by **domain** rather than by **type**:

```
src/egregora/
├── llm/                        # All LLM-related code
│   ├── __init__.py
│   ├── client.py               # Client abstraction
│   ├── batch.py                # Batch processing (from utils/)
│   ├── gemini.py               # Gemini-specific (merge genai.py + gemini_dispatcher.py)
│   ├── dispatcher.py           # Base dispatcher (from utils/)
│   └── prompts.py              # Prompt helpers
│
├── storage/                    # Data persistence
│   ├── __init__.py
│   ├── serialization.py        # Table I/O (from utils/)
│   ├── cache.py                # Caching (from utils/)
│   ├── checkpoints.py          # Checkpoints (from utils/)
│   └── formats.py              # Format detection
│
├── filesystem/                 # File operations
│   ├── __init__.py
│   ├── paths.py                # Path helpers (from utils/)
│   └── archives.py             # ZIP utilities (from utils/)
│
├── logging/                    # Logging & observability
│   ├── __init__.py
│   ├── setup.py                # Logging setup (from utils/)
│   └── logfire.py              # Logfire config (from utils/)
│
└── utils/                      # Actually generic utilities
    ├── __init__.py
    └── text.py                 # String manipulation, etc.
```

### Migration Strategy

1. **Phase 1**: Create new directories, copy files
2. **Phase 2**: Update imports gradually (module by module)
3. **Phase 3**: Keep aliases in old locations for compatibility
4. **Phase 4**: Remove aliases after deprecation period

### Implementation Checklist

- [ ] Create new directory structure
- [ ] Move LLM-related files to `llm/`
- [ ] Move storage files to `storage/`
- [ ] Move filesystem files to `filesystem/`
- [ ] Move logging files to `logging/`
- [ ] Create import aliases for backward compatibility
- [ ] Update documentation
- [ ] Gradually migrate imports
- [ ] Remove old utils files after deprecation

---

## 7. TODO Comments 🟢 Low Priority

### Incomplete Features

```python
# src/egregora/ingestion/slack_input.py:172
# TODO: Implement media download using Slack API

# src/egregora/ingestion/slack_input.py:283
# Handle file attachments (TODO: download files)

# src/egregora/rendering/hugo.py:87
# TODO: Use `hugo new site` command or create manually

# src/egregora/rendering/hugo.py:165
site_name="Hugo Site",  # TODO: Parse from config

# src/egregora/rendering/hugo.py:299
# TODO: Parse TOML config
```

### Recommendation

Convert TODOs to GitHub issues for tracking:

```markdown
## Issue Template

**Title**: Implement Slack media downloads

**Description**:
Currently, Slack media attachments are not downloaded. We need to:
1. Use Slack API to download file attachments
2. Store in media directory with proper naming
3. Update media reference tracking

**Location**: `src/egregora/ingestion/slack_input.py:172, 283`

**Priority**: Medium

**Labels**: enhancement, slack-integration
```

---

## 8. Missing Docstrings 🟡 Medium Priority

### Undocumented Public APIs

Found 15+ public functions/classes without docstrings:

- `prompt_templates.py` - Multiple `render()` functions
- `cli.py:571` - `rank()` command
- `agents/resolver.py:61` - `AgentResolver` class
- `agents/models.py` - Data model classes
- `agents/writer/writer_agent.py:72` - `WritePostResult` class

### Documentation Standard

Adopt Google-style docstrings:

```python
def rank(
    site_path: Path,
    comparisons: int = 10,
    debug: bool = False,
) -> None:
    """
    Run interactive ranking session to compare posts.

    Presents pairs of posts to the user and records their preferences
    using an ELO rating system. Rankings are persisted to the database
    and can be used to select top content.

    Args:
        site_path: Path to the site directory containing posts and database.
        comparisons: Number of post pairs to compare. Defaults to 10.
        debug: If True, show full tracebacks on errors. Defaults to False.

    Raises:
        ValueError: If site_path doesn't exist or contains no posts.
        FileNotFoundError: If required database tables are missing.

    Example:
        >>> rank(Path("./my-site"), comparisons=20)
        # Starts interactive ranking session
    """
```

---

## 9. Suppressed Linter Warnings 🟡 Medium Priority

### Code Smells Hidden with `noqa`

**File**: `src/egregora/pipeline.py:146`
```python
def _process_whatsapp_export(  # noqa: PLR0912, PLR0913, PLR0915
```

**Suppressed warnings**:
- `PLR0912` - Too many branches (complex logic)
- `PLR0913` - Too many arguments (16 parameters!)
- `PLR0915` - Too many statements (function too long)

### Recommendation

**Don't suppress warnings - fix them!**

The refactorings proposed in sections 2 and 3 will eliminate the need for these `noqa` comments by addressing the root causes.

---

## Summary: What's Already Good ✅

Your codebase avoids many common Python anti-patterns:

✅ **No mutable default arguments** - All function signatures are safe
✅ **No unnecessary conditions** - No `if x == True:` or `return True if cond else False`
✅ **No string concatenation in loops** - Proper use of join/formatting
✅ **No index gymnastics** - Good use of `enumerate()` and comprehensions
✅ **Absolute imports** - No confusing relative imports
✅ **Good constants** - Module-level constants are well-defined
✅ **Type hints** - Most functions have proper type annotations
✅ **No bare `except:`** - At least specifies `Exception` (though still too broad)

---

## Implementation Priority Matrix

### Week 1: High-Impact Fixes
| Task | Effort | Impact | Risk |
|------|--------|--------|------|
| Fix 7 bare exceptions | 2h | High | Low |
| Create config dataclasses | 3h | High | Low |
| Refactor parameter lists | 4h | High | Medium |

### Week 2: Major Refactoring
| Task | Effort | Impact | Risk |
|------|--------|--------|------|
| Refactor `enrich_table()` | 8h | Very High | High |
| Extract nested loops | 3h | Medium | Low |
| Create constants module | 1h | Medium | Low |

### Week 3: Structural Improvements
| Task | Effort | Impact | Risk |
|------|--------|--------|------|
| Reorganize utils/ | 3h | Medium | Medium |
| Add docstrings | 2h | Medium | Low |
| Convert TODOs to issues | 1h | Low | Low |

---

## Testing Strategy

For each refactoring:

1. **Characterization tests**: Capture current behavior
2. **Parallel implementation**: Run old and new side-by-side
3. **Comparison validation**: Assert outputs match
4. **Feature flag**: Toggle between implementations
5. **Gradual rollout**: Enable for subset of use cases first

Example:
```python
# Feature flag approach
USE_NEW_ENRICHMENT = os.getenv("EGREGORA_NEW_ENRICHMENT", "false").lower() == "true"

def enrich_table(...):
    if USE_NEW_ENRICHMENT:
        return _enrich_table_v2(...)
    else:
        return _enrich_table_legacy(...)
```

---

## Linter Configuration

Add to `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "PLR", # pylint refactor
    "SIM", # flake8-simplify
]

[tool.ruff.lint.pylint]
max-args = 7              # Flag functions with >7 parameters
max-branches = 12         # Flag complex branching
max-statements = 50       # Flag long functions
max-nested-blocks = 4     # Flag deep nesting

[tool.mypy]
strict = true
warn_unused_ignores = true
warn_return_any = true
```

---

## Conclusion

The Egregora codebase shows good fundamentals but has accumulated technical debt in a few concentrated areas. The proposed refactorings will:

1. **Improve maintainability** - Smaller, focused functions
2. **Increase testability** - Clear abstractions with defined responsibilities
3. **Enhance extensibility** - Easy to add new enrichment types, plugins, etc.
4. **Reduce bugs** - Specific exception handling catches real issues

**Estimated total effort**: 23 hours over 3 weeks

The highest priority is refactoring `enrich_table()` and fixing the bare exception handlers, as these affect reliability and debuggability.
