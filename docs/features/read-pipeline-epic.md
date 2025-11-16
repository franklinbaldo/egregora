# Read Pipeline Epic Plan

**Status:** Planning
**Target:** Phase 9+ (2025-02)
**Tracking:** TBD

## Overview

This document outlines the epic plan to rebuild the **Reader Agent Pipeline** (formerly "ranking agent"), which enables quality feedback and post evaluation through AI-powered post comparisons and ELO-based ratings.

## Historical Context

### What Was the Ranking/Reader Agent?

The ranking agent was a Pydantic AI-powered system that:

1. **Simulated reader feedback** on blog posts through pairwise comparisons
2. **Calculated ELO ratings** to rank post quality over time
3. **Collected structured feedback** (comments + star ratings) from simulated readers
4. **Built quality metrics** through iterative comparisons

### Original Implementation (Removed in `fb78daa`)

**Files:**
- `src/egregora/agents/ranking/agent.py` (552 lines) - Pydantic AI agent with three-turn protocol
- `src/egregora/agents/ranking/elo.py` (146 lines) - ELO rating calculation system
- `src/egregora/agents/ranking/store.py` - DuckDB-backed ranking store

**CLI Command:**
```bash
egregora rank --site-dir=. --comparisons=50
```

**Architecture:**
```
1. Agent selects two posts (strategy: "fewest_games")
2. Loads post content + author profiles
3. Three-turn conversation:
   Turn 1: choose_winner_tool("A" or "B")
   Turn 2: comment_post_a_tool(comment, stars)
   Turn 3: comment_post_b_tool(comment, stars)
4. Updates ELO ratings (K-factor=32, default=1500)
5. Saves comparison to DuckDB (elo_history table)
6. Optionally exports to Parquet
```

### Why It Was Removed

**Reason:** Non-functional in current architecture

From commit message `fb78daa`:
> "Removed non-functional agents and unnecessary CLI commands to streamline the codebase"

**Specific issues:**
1. **Incompatible with current architecture** - Used old patterns (google.genai instead of pydantic-ai, old config system)
2. **Not integrated with orchestration layer** - Existed before `orchestration/` was created
3. **Missing modern features** - No Document abstraction, no OutputAdapter integration
4. **Dead code** - Tests passing but functionality not used

### Rename Proposal: "rank" → "reader"

From commit `d1c036d`:

**Rationale:**
- **More descriptive**: "reader agent" reads the blog and gives feedback
- **User-centric naming**: Matches mental model of "what would a reader think?"
- **Clearer than "ranking"**: Which implies sorting/ordering rather than feedback

**Proposed usage:**
```bash
egregora reader --site-dir=. --feedback-rounds=50
```

## The New Read Pipeline

### Vision

Build a **Read Pipeline** that enables:

1. **Quality evaluation** - AI simulates readers evaluating post quality
2. **Post discovery** - Helps users explore and understand existing posts
3. **Content insights** - Provides analytics on what content resonates
4. **Iterative improvement** - Feedback loop for content quality

### Core Capabilities

#### 1. **Reader Agent** (Quality Feedback)
- Pairwise post comparisons with structured feedback
- ELO-based quality rankings
- Persona-based evaluation (different reader profiles)
- Comment aggregation and trend analysis

#### 2. **Explorer Agent** (Content Discovery)
- Query existing posts semantically
- Find related conversations
- Explore topic clusters
- Timeline navigation

#### 3. **Analyst Agent** (Insights)
- Quality trends over time
- Topic popularity analysis
- Author contribution metrics
- Engagement simulation

## Architecture Integration

### Modern Orchestration Pattern

Following the current three-layer architecture:

```
orchestration/
  ├── write_pipeline.py      # EXISTS - Generate new posts
  ├── read_pipeline.py       # NEW - Evaluate existing posts
  └── edit_pipeline.py       # FUTURE - Refine content

data_primitives/
  ├── document.py            # EXISTS - Core abstraction
  └── reader_models.py       # NEW - Reader-specific models

agents/
  ├── shared/
  │   └── annotations/       # EXTEND - unified annotation storage
  │       ├── store.py       # Persist writer + reader feedback
  │       └── models.py
  └── reader/                # NEW
      ├── agent.py           # Pydantic AI reader agent
      ├── elo.py             # ELO rating system (pure functions)
      ├── elo_store.py       # Aggregated ELO ratings
      └── strategies.py      # Selection strategies
```

### Integration Points

#### With Existing Systems

**Document Abstraction:**
```python
# Reader works with Document objects
from egregora.data_primitives import Document, DocumentType

# Load posts via OutputAdapter
posts = output_adapter.list_documents(doc_type=DocumentType.POST)
```

**OutputAdapter (CRITICAL - Format Independence):**

The reader CLI **MUST use OutputAdapter** to read posts, not hardcode MkDocs/Hugo paths.

```python
# List all documents (returns Ibis table)
docs_table = output_adapter.list_documents()
# → storage_identifier (e.g., "posts/2025-01-10-post.md"), mtime_ns

# Resolve identifier to filesystem path
for doc in docs_table.execute().itertuples():
    path = output_adapter.resolve_document_path(doc.storage_identifier)
    content = path.read_text()
    metadata, body = output_adapter.parse_frontmatter(content)
    # Now have: post title, date, tags, etc. + content

# Use storage properties for type-specific access
posts_storage = output_adapter.posts
profile_storage = output_adapter.profiles
```

**Why this matters:**
- ✅ Works with MkDocs, Hugo, Database backends, S3 storage
- ✅ No hardcoded paths (filesystem-agnostic)
- ✅ Future-proof (new formats need zero reader changes)

**RAG/Vector Store:**
```python
# Reuse RAG infrastructure for semantic search
from egregora.agents.shared.rag import VectorStore

# Find similar posts for context
similar = store.search(post_embedding, top_k=5)
```

**Run Tracking:**
```python
# Integrate with observability
from egregora.database.tracking import track_run_event

track_run_event("reader_comparison", metadata={
    "post_a": post_a_id,
    "post_b": post_b_id,
    "winner": winner,
})
```

## Implementation Plan

### Phase 1: Core Infrastructure

**Goal:** Restore basic ranking functionality with modern patterns

**Tasks:**

1. **Create reader agent module** (`agents/reader/`)
   - Port `agent.py` to use current Pydantic AI patterns
   - Update to use `Document` abstraction
   - Integrate with current config system (`EgregoraConfig`)

2. **Modernize ELO system** (`agents/reader/elo.py`)
   - Port ELO calculation logic
   - Add type annotations (Annotated with descriptions)
   - Support multiple rating strategies (global, per-author, per-topic)
   - Provide helpers for `elo_store.py` to persist aggregated ratings derived from annotation history

3. **Extend AnnotationStore for reader feedback** (`agents/shared/annotations/store.py`)
   - **Reuse existing annotation infrastructure** for reader comments
   - Add `annotation_type` to metadata to distinguish reader feedback from writer notes
   - Store stars, comparison context, reader profile in `metadata` JSON field
   - Tag reader feedback via `annotation_type="reader_feedback"`
   - Preserve unified DuckDB persistence alongside writer annotations
   ```python
   # Save reader feedback as annotation
   annotation_store.save_annotation(
       document_id=post_id,
       source="reader_agent",
       content=comment_text,
       metadata={
           "annotation_type": "reader_feedback",
           "stars": 4,
           "comparison_id": "cmp-abc123",
           "reader_profile_id": "profile-uuid",
           "winner": "A"
       }
   )
   ```

4. **Create lightweight EloStore** (`agents/reader/elo_store.py`)
   - **Separate store for computed aggregates only** (ELO ratings)
   - DuckDB-backed, much simpler than original RankingStore
   - Just tracks: post_id, elo_global, elo_by_profile, games_played
   - **Not for comments** (those go in AnnotationStore)

5. **Define reader models** (`data_primitives/reader_models.py`)
   ```python
   @dataclass(frozen=True, slots=True)
   class Comparison:
       """Result of a reader comparison between two posts."""
       comparison_id: str
       timestamp: datetime
       reader_profile_id: str
       post_a_id: str
       post_b_id: str
       winner: Literal["A", "B"]
       comment_a: str
       stars_a: int  # 1-5
       comment_b: str
       stars_b: int  # 1-5

   @dataclass(frozen=True, slots=True)
   class PostRating:
       """ELO rating and metadata for a post."""
       post_id: str
       elo_global: float
       elo_by_profile: dict[str, float]  # Per-reader ratings
       games_played: int
       last_updated: datetime
   ```

**Tests:**
- Unit tests for ELO calculation
- Integration tests for store (DuckDB CRUD)
- Agent tests with VCR cassettes

**Deliverable:** `egregora.agents.reader` module working standalone

---

### Phase 2: Orchestration Layer

**Goal:** Create `read_pipeline.py` following `write_pipeline.py` patterns

**Tasks:**

1. **Create read pipeline orchestration** (`orchestration/read_pipeline.py`)
   ```python
   def run(
       site_dir: Path,
       feedback_rounds: int = 50,
       strategy: str = "fewest_games",
       reader_profile: Path | None = None,
       config: EgregoraConfig | None = None,
   ) -> ReadPipelineResult:
       """Execute the read pipeline workflow.

       1. Initialize OutputAdapter (format-independent!)
       2. Load existing posts via OutputAdapter.list_documents()
       3. Select posts to compare (via strategy)
       4. Run reader agent comparisons
       5. Update ELO ratings
       6. Generate insights/reports

       CRITICAL: Uses OutputAdapter for format independence.
       Works with MkDocs, Hugo, Database, S3, etc.
       """
       # Step 1: Initialize OutputAdapter
       from egregora.output_adapters import output_registry

       output_adapter = output_registry.detect_format(site_dir)
       if not output_adapter:
           raise ValueError(f"No output format detected for {site_dir}")

       output_adapter.initialize(site_dir)

       # Step 2: Load posts (format-independent!)
       docs_table = output_adapter.list_documents()
       posts = []
       for doc in docs_table.execute().itertuples():
           path = output_adapter.resolve_document_path(doc.storage_identifier)
           content = path.read_text()
           metadata, body = output_adapter.parse_frontmatter(content)
           posts.append({
               "post_id": Path(doc.storage_identifier).stem,
               "title": metadata.get("title"),
               "content": body,
               "metadata": metadata,
           })

       # Step 3: Initialize stores (unified architecture)
       from egregora.agents.shared.annotations import AnnotationStore
       from egregora.agents.reader.elo_store import EloStore

       annotation_store = AnnotationStore(site_dir / ".egregora" / "annotations.db")
       elo_store = EloStore(site_dir / ".egregora" / "elo_ratings.db")

       # Step 4: Run comparisons
       from egregora.agents.reader import ReaderAgent

       reader = ReaderAgent(model=config.reader.model)

       for round_num in range(feedback_rounds):
           # Select posts via strategy
           post_a, post_b = select_posts(posts, strategy, elo_store)

           # Run three-turn comparison
           result = reader.compare_posts(
               post_a=post_a,
               post_b=post_b,
               reader_profile=reader_profile
           )

           # Step 5: Save feedback to AnnotationStore (unified!)
           annotation_store.save_annotation(
               document_id=post_a["post_id"],
               source="reader_agent",
               content=result.comment_a,
               metadata={
                   "annotation_type": "reader_feedback",
                   "stars": result.stars_a,
                   "comparison_id": result.comparison_id,
                   "reader_profile_id": result.reader_profile_id,
                   "winner": result.winner
               }
           )

           annotation_store.save_annotation(
               document_id=post_b["post_id"],
               source="reader_agent",
               content=result.comment_b,
               metadata={
                   "annotation_type": "reader_feedback",
                   "stars": result.stars_b,
                   "comparison_id": result.comparison_id,
                   "reader_profile_id": result.reader_profile_id,
                   "winner": result.winner
               }
           )

           # Step 6: Update ELO ratings in EloStore
           elo_store.update_ratings(
               post_a_id=post_a["post_id"],
               post_b_id=post_b["post_id"],
               winner=result.winner,
               reader_profile_id=result.reader_profile_id
           )

       # Step 7: Generate insights (query both stores)
       ...
   ```

2. **Define selection strategies** (`agents/reader/strategies.py`)
   - `fewest_games` - Prioritize under-evaluated posts
   - `random` - Random sampling
   - `diversity` - Maximize topic/author diversity
   - `top_vs_bottom` - Compare extremes
   - `temporal` - Recent vs old posts

3. **Reader profile system**
   - Reuse author profile format
   - Default "general reader" profile
   - Custom profiles for different perspectives (e.g., technical, casual, domain expert)

4. **Progress tracking & observability**
   - Log comparisons to run tracking
   - Real-time stats (comparisons completed, ELO spread, etc.)
   - Checkpoint/resume support

**Tests:**
- E2E test with test site
- Strategy selection tests
- Profile loading tests

**Deliverable:** `orchestration.read_pipeline.run()` working end-to-end

---

### Phase 3: CLI Integration

**Goal:** Add `egregora reader` command

**Tasks:**

1. **Add reader CLI** (`cli.py`)
   ```bash
   egregora reader --site-dir=./output --feedback-rounds=50
   egregora reader --site-dir=./output --strategy=diversity --rounds=20
   egregora reader --site-dir=./output --profile=./expert.md
   ```

2. **CLI options:**
   - `--site-dir` - Site directory to evaluate
   - `--feedback-rounds` (or `--rounds`) - Number of comparisons
   - `--strategy` - Post selection strategy
   - `--profile` - Reader profile path
   - `--export` - Export rankings to Parquet
   - `--show-stats` - Display ranking statistics

3. **Interactive mode** (optional)
   ```bash
   egregora reader --interactive
   # Shows post pairs, gets LLM feedback in real-time
   # Displays running ELO rankings
   # User can interrupt and resume
   ```

**Tests:**
- CLI integration tests
- Help text validation
- Error handling

**Deliverable:** `egregora reader` command fully functional

---

### Phase 4: Analytics & Insights

**Goal:** Generate meaningful insights from ranking data

**Tasks:**

1. **Ranking analytics** (`agents/reader/analytics.py`)
   ```python
   def generate_ranking_report(
       elo_store: EloStore,
       annotation_store: AnnotationStore
   ) -> RankingReport:
       """Generate comprehensive ranking insights.

       Queries both stores for unified analysis:
       - elo_store: ELO ratings, games played
       - annotation_store: Reader feedback comments and stars

       Returns:
           - Top 10 posts by ELO
           - Most improved posts
           - Consensus posts (high agreement across readers)
           - Controversial posts (high variance in ratings)
           - Quality trends over time
           - Best/worst comments per post
       """
       # Query ELO ratings
       top_posts = elo_store.get_top_posts(limit=10)

       # Query reader feedback from annotations
       for post in top_posts:
           feedback = annotation_store.get_annotations(
               document_id=post.post_id,
               filters={"annotation_type": "reader_feedback"}
           )
           # Aggregate stars, extract representative comments
           ...
   ```

2. **Visualization exports**
   - Export data for external visualization (Parquet)
   - Generate simple markdown tables
   - (Future) Generate charts via matplotlib/plotly

3. **Integration with OutputAdapter**
   - Option to write ranking metadata to frontmatter
   - Generate `rankings.md` page in site
   - Update post pages with quality badges

**Tests:**
- Analytics calculation tests
- Export format validation

**Deliverable:** `egregora reader --report` generates insights

---

### Phase 5: Advanced Features

**Goal:** Extend beyond basic ranking

**Tasks:**

1. **Explorer Agent** (`agents/explorer/`)
   - Semantic search across posts
   - Topic clustering
   - Conversation thread discovery
   - Timeline exploration

2. **Analyst Agent** (`agents/analyst/`)
   - Content quality trends
   - Topic evolution over time
   - Author contribution analysis
   - Engagement forecasting

3. **Multi-reader perspectives**
   - Compare ratings from different reader profiles
   - Identify posts that appeal to specific audiences
   - Diversity metrics (does content serve all readers?)

4. **Feedback integration with write pipeline**
   - Use ranking data to inform writer agent
   - "Top posts on similar topics" in RAG context
   - Quality benchmarks for new posts

**Tests:**
- Per-agent test suites
- Integration tests with write pipeline

**Deliverable:** Full read pipeline ecosystem

---

## Database Schema

### Unified Architecture: Two Stores

**1. AnnotationStore** (existing, extend for reader feedback)
- **Purpose**: Store all commentary (writer notes + reader feedback)
- **Location**: `agents/shared/annotations/store.py`
- **Schema**: `ANNOTATIONS_SCHEMA` (already exists in `database/ir_schema.py`)

Reader feedback stored via `annotation_type` metadata:
```python
{
    "document_id": "post-2025-01-10-example",
    "source": "reader_agent",
    "content": "Great post! Clear explanations and good examples.",
    "metadata": {
        "annotation_type": "reader_feedback",      # Distinguish from writer notes
        "stars": 4,                                # 1-5 rating
        "comparison_id": "cmp-abc123",            # Link to comparison
        "reader_profile_id": "profile-uuid",      # Which reader persona
        "winner": "A"                             # If this post won comparison
    }
}
```

**2. EloStore** (new, lightweight)
- **Purpose**: Store computed ELO ratings only (not comments)
- **Location**: `agents/reader/elo_store.py`
- **Schemas**: `ELO_RATINGS_SCHEMA` + `ELO_HISTORY_SCHEMA`

### ELO Ratings Table (EloStore)

```sql
CREATE TABLE elo_ratings (
    post_id VARCHAR PRIMARY KEY,           -- Post slug
    elo_global DOUBLE NOT NULL DEFAULT 1500,
    elo_by_profile JSON,                   -- {"profile-uuid": 1550.5, ...}
    games_played INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_ratings_elo ON elo_ratings(elo_global);
CREATE INDEX idx_ratings_games ON elo_ratings(games_played);
```

### ELO History Table (EloStore)

Tracks ELO changes over time (NOT comments - those are in AnnotationStore):

```sql
CREATE TABLE elo_history (
    comparison_id VARCHAR PRIMARY KEY,
    annotation_id VARCHAR NOT NULL,        -- FK into annotations table
    timestamp TIMESTAMP NOT NULL,
    reader_profile_id VARCHAR NOT NULL,   -- UUID of reader persona
    post_a VARCHAR NOT NULL,
    post_b VARCHAR NOT NULL,
    winner VARCHAR NOT NULL CHECK (winner IN ('A', 'B')),
    elo_a_before DOUBLE,                   -- Track ELO changes
    elo_a_after DOUBLE,
    elo_b_before DOUBLE,
    elo_b_after DOUBLE
);

CREATE INDEX idx_history_post_a ON elo_history(post_a);
CREATE INDEX idx_history_post_b ON elo_history(post_b);
CREATE INDEX idx_history_annotation ON elo_history(annotation_id);
CREATE INDEX idx_history_timestamp ON elo_history(timestamp);
CREATE INDEX idx_history_reader ON elo_history(reader_profile_id);
```

**Note:** Original schema had `comment_a`, `stars_a`, `comment_b`, `stars_b` columns.
These now live in AnnotationStore (linked via `comparison_id`).

### Location

Update the existing `ELO_RATINGS_SCHEMA` and `ELO_HISTORY_SCHEMA` entries in
`src/egregora/database/ir_schema.py` to match the new structure. Apply the
changes in place so the centralized schema module stays the single source of
truth.

**`ELO_RATINGS_SCHEMA` adjustments**

- ➕ Add `elo_by_profile` (`dt.json`) to store per-reader persona scores.
- 🔁 Rename `num_comparisons` → `games_played` (`dt.int64`).
- ➕ Add `created_at` (`dt.Timestamp(timezone="UTC")`) alongside `last_updated`.

**`ELO_HISTORY_SCHEMA` adjustments**

- 🔁 Replace `winner_id`/`loser_id` with `post_a`, `post_b`, and `winner` (all
  `dt.string`).
- ➖ Remove the `tie` flag; ties are represented through the new winner logic.
- ➖ Remove `elo_change` and instead ➕ add
  `elo_a_before`/`elo_a_after`/`elo_b_before`/`elo_b_after` (`dt.float64`).
- ➕ Add `reader_profile_id` (`dt.string`) for persona tracking.
- ➕ Add structured feedback fields: `comment_a`, `comment_b` (`dt.string`) and
  `stars_a`, `stars_b` (`dt.int64`).
Update the existing constants in `database/ir_schema.py` so their definitions include the new fields:

```python
ELO_RATINGS_SCHEMA = ibis.schema({
    "post_id": dt.string,
    "elo_global": dt.float64,
    "elo_by_profile": dt.json,
    "games_played": dt.int64,
    "last_updated": dt.Timestamp(timezone="UTC"),
    "created_at": dt.Timestamp(timezone="UTC"),
})

ELO_HISTORY_SCHEMA = ibis.schema({
    "comparison_id": dt.string,
    "annotation_id": dt.string,
    "timestamp": dt.Timestamp(timezone="UTC"),
    "reader_profile_id": dt.string,
    "post_a": dt.string,
    "post_b": dt.string,
    "winner": dt.string,
    "elo_a_before": dt.float64,
    "elo_a_after": dt.float64,
    "elo_b_before": dt.float64,
    "elo_b_after": dt.float64,
})
```

**Migration considerations**

- DuckDB tables created from the previous schema will need `ALTER TABLE`
  operations (or table recreation) to add, rename, and drop the columns listed
  above.
- Backfill scripts must populate the new fields (for example, initialize
  `elo_by_profile` with an empty JSON object and carry over
  `num_comparisons` → `games_played`).
- Historical records need transformation to split `winner_id`/`loser_id` into
  `post_a`/`post_b`/`winner` fields and compute before/after ELO values prior to
  inserting into the updated history table.
> **Migration note:** Alter the corresponding DuckDB tables (or rebuild them) so the additional columns and JSON payloads exist before enabling the reader pipeline.

Pairwise “games” should remain queryable via the annotation store. Each reader comparison persists a unified annotation record containing the comparison identifier, the two post ids, the winner, and the structured metadata. ELO aggregates in `elo_store.py` can then recompute ratings from the full history when needed.

## Configuration

Add to `config/settings.py`:

```python
class ReaderSettings(BaseModel):
    """Reader agent configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable the reader pipeline",
    )
    model: PydanticModelName = Field(
        default=DEFAULT_MODEL,
        description="Model used for reader/feedback comparisons",
    )
    default_strategy: str = Field(
        default="fewest_games",
        description="Default post selection strategy",
    )
    k_factor: int = Field(
        default=32,
        ge=1,
        description="ELO K-factor",
    )
    default_elo: float = Field(
        default=1500.0,
        description="Starting ELO score for posts",
    )
    min_stars: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Minimum star rating",
    )
    max_stars: int = Field(
        default=5,
        ge=1,
        le=5,
        description="Maximum star rating",
    )
    max_comment_length: int = Field(
        default=250,
        ge=0,
        description="Maximum feedback comment length",
    )
    feedback_rounds_default: int = Field(
        default=50,
        ge=1,
        description="Default number of feedback comparisons per run",
    )
from pydantic import BaseModel, Field


class ReaderSettings(BaseModel):
    """Reader agent configuration."""

    enabled: bool = Field(default=True, description="Enable the reader pipeline")
    model: str = Field(default="google-gla:gemini-2.0-flash-exp")
    default_strategy: str = Field(default="fewest_games")
    k_factor: int = Field(default=32, description="ELO K-factor")
    default_elo: float = Field(default=1500.0)
    min_stars: int = Field(default=1)
    max_stars: int = Field(default=5)
    max_comment_length: int = Field(default=250)
    feedback_rounds_default: int = Field(default=50)


class EgregoraConfig(BaseModel):
    # ... existing fields ...
    reader: ReaderSettings = Field(
        default_factory=ReaderSettings,
        description="Reader agent configuration",
    )
```

`load_egregora_config` and `create_default_config` already rely on `EgregoraConfig(**data)` and `EgregoraConfig()` respectively, so no additional logic is required—adding the `reader` field ensures the new defaults are injected whenever the section is missing from disk, and `save_egregora_config` will persist the populated values automatically.

Update `.egregora/config.yml` defaults to align with the Pydantic schema:
    reader: ReaderSettings = Field(default_factory=ReaderSettings)
```

Update any config loader helpers (e.g., `load_egregora_config`) so they continue to round-trip the new `reader` section.

Add to `.egregora/config.yml`:

```yaml
reader:
  enabled: true
  model: google-gla:gemini-flash-latest
  default_strategy: fewest_games
  k_factor: 32
  default_elo: 1500.0
  min_stars: 1
  max_stars: 5
  max_comment_length: 250
  feedback_rounds_default: 50
```

## Benefits

### For Content Creators

1. **Quality feedback** - Understand what content resonates
2. **Objective ranking** - ELO-based quality metrics
3. **Trend analysis** - See quality improvements over time
4. **Topic insights** - Which topics perform best

### For Developers

1. **Modern architecture** - Built on current orchestration patterns
2. **Reusable components** - Integrates with Document, OutputAdapter, RAG
3. **Extensible** - Easy to add new strategies, agents, analytics
4. **Observable** - Full run tracking and metrics

### For Users

1. **Content discovery** - Find high-quality posts
2. **Diverse perspectives** - Compare ratings from different reader profiles
3. **Transparency** - See why posts are rated highly (comments)

## Migration from Old System

**Backward compatibility:** Not required (alpha mindset)

**Data migration:** If old ranking data exists, create migration script:
```python
# scripts/migrate_old_rankings.py
def migrate_rankings(old_db: Path, new_db: Path):
    """Migrate ELO ratings from old schema to new."""
    # Read old elo_ratings, elo_history
    # Transform to new schema (add reader_profile_id, elo_by_profile)
    # Write to new database
```

## Testing Strategy

### Unit Tests
- ELO calculation (pure functions)
- Strategy selection logic
- Comment truncation/validation

### Integration Tests
- DuckDB store CRUD operations (`tests/integration/test_reader_store.py`)
- Reader agent with VCR cassettes
- Profile loading
- Reader pipeline orchestration (`tests/integration/test_read_pipeline.py`)

### E2E Tests
- Full read pipeline on test site
- Multiple feedback rounds
- Export to Parquet

### Performance Tests
- 1000+ post ranking
- Concurrent comparisons
- Database query performance

## Documentation

### User Docs
- `docs/guide/reader-agent.md` - User guide
- `docs/cli/reader-command.md` - CLI reference

### Developer Docs
- `docs/architecture/read-pipeline.md` - Architecture overview
- `docs/agents/reader.md` - Agent implementation details
- `docs/database/elo-schema.md` - Schema documentation

### Examples
- `examples/reader-profiles/` - Example reader profiles
- `examples/ranking-reports/` - Sample analytics outputs

## Open Questions

1. **Should we support human feedback?**
   - Mix AI + human comparisons?
   - Weight human feedback higher?

2. **How to handle post updates?**
   - Reset ELO when content changes significantly?
   - Track ELO per version?

3. **Multi-model evaluation?**
   - Compare ratings from different LLMs?
   - Ensemble approach?

4. **Real-time vs batch?**
   - Run reader agent on every new post?
   - Or batch comparisons periodically?

## Success Metrics

**Phase 1 Success:**
- ✅ Reader agent completes pairwise comparisons
- ✅ ELO ratings update correctly
- ✅ Tests passing (unit, integration)

**Phase 2 Success:**
- ✅ `read_pipeline.run()` executes full workflow
- ✅ Strategies select posts correctly
- ✅ Checkpointing works

**Phase 3 Success:**
- ✅ `egregora reader` command works
- ✅ User can evaluate 50+ posts
- ✅ Stats display correctly

**Phase 4 Success:**
- ✅ Analytics generate meaningful insights
- ✅ Reports exportable to Parquet/Markdown
- ✅ Integration with site structure

**Phase 5 Success:**
- ✅ Explorer agent discovers content
- ✅ Analyst agent provides trends
- ✅ Feedback improves write pipeline

## Timeline Estimate

**Phase 1:** 3-5 days (core infrastructure)
**Phase 2:** 2-3 days (orchestration)
**Phase 3:** 1-2 days (CLI)
**Phase 4:** 2-3 days (analytics)
**Phase 5:** 5-7 days (advanced features)

**Total:** 2-3 weeks for full implementation

## References

- Original ranking agent: `git show fb78daa^:src/egregora/agents/ranking/`
- Rename proposal: `git show d1c036d`
- Current write pipeline: `src/egregora/orchestration/write_pipeline.py`
- Document abstraction: `src/egregora/data_primitives/document.py`
- Reader store integration tests: `tests/integration/test_reader_store.py`
- Reader pipeline integration tests should live in `tests/integration/test_reader_pipeline.py`
