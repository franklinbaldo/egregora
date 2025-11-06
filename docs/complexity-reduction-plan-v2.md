# Complexity Reduction Plan v2.0 - Modern Patterns & Large Refactor

## Executive Summary

This document evaluates and significantly improves upon the original complexity reduction plan (PR #618) with:

1. **Modern Pydantic-AI patterns** - Align with standard agent architecture practices
2. **Industry-standard parsing** - Replace regex with parser combinators (pyparsing)
3. **Large-scale refactoring** - More ambitious architectural improvements
4. **Better separation of concerns** - Clear domain boundaries and responsibilities

**Current State**: 62 complexity errors
**Target State**: 0 complexity errors + modernized architecture
**Timeline**: 8-10 weeks (vs. 6 weeks in original plan, but with much better outcomes)

---

## Part 1: Evaluation of Original Plan

### ✅ Strengths

1. **Good tactical approaches**: Config objects, strategy pattern, query builders are solid
2. **Systematic breakdown**: Clear categorization by error type
3. **Testability focus**: Emphasis on maintaining test coverage
4. **Incremental delivery**: Weekly phases reduce risk

### ⚠️ Gaps & Missed Opportunities

#### Gap 1: **Parsing Architecture is Fundamentally Flawed**

**Current approach** (`src/egregora/ingestion/parser.py`):
- Complex regex patterns (lines 331-333): `_LINE_PATTERN = re.compile(...)`
- Manual state management with `_MessageBuilder`
- Fragile date parsing with multiple fallbacks
- High cyclomatic complexity (C901: 15 in `parse_multiple`)

**Industry standard** would use:
- **Parser combinators** (pyparsing, parsy, lark)
- **Formal grammar** for WhatsApp message format
- **Dataclass-based AST** for intermediate representation
- **Separate validation from parsing** logic

**Original plan**: Only addresses symptoms (PLR0912, C901) via visitor pattern
**Should do**: Complete parsing rewrite with modern parser library

#### Gap 2: **Pydantic-AI Agent Architecture Not Fully Leveraged**

**Current issues** (`src/egregora/agents/writer/writer_agent.py`):

```python
# ❌ Current: Massive function signatures (14 parameters!)
def write_posts_with_pydantic_agent(
    prompt: str,
    model_name: str,
    period_date: str,
    output_dir: Path,
    profiles_dir: Path,
    rag_dir: Path,
    client: object,
    embedding_model: str,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
    annotations_store: AnnotationStore | None,
    agent_model: object | None = None,
    register_tools: bool = True,
) -> tuple[list[str], list[str]]:
```

**Standard Pydantic-AI pattern**:
- Use `RunContext` with proper dependency injection
- Agent state should be immutable (use `frozenset`, not `list`)
- Tool registration should be declarative, not imperative
- Use `Result` types for error handling (already have `returns` package!)

**Original plan**: Config objects reduce to 3 params, but doesn't fix architectural issues
**Should do**: Complete agent rewrite following Pydantic-AI best practices

#### Gap 3: **RAG Search is Monolithic**

**Current** (`src/egregora/agents/tools/rag/store.py:436`):
- 21 cyclomatic complexity
- 77 statements in one function
- 10 parameters
- 7 return statements

**Original plan**: Query builder pattern
**Better approach**:
- **Separate retrieval strategies** (ANNRetriever, ExactRetriever)
- **Filter chain pattern** (composable filters)
- **Search pipeline** (embed → retrieve → filter → rank → limit)
- **Result monad** for error handling instead of early returns

#### Gap 4: **No Use of Type System for Complexity Reduction**

**Opportunities missed**:
- **Algebraic Data Types (ADTs)** - Use enums/unions to eliminate branching
- **NewTypes** - Domain primitives (AuthorUUID, MessageID, etc.)
- **Protocols** - Interface segregation
- **Type guards** - Type narrowing reduces defensive checks

Example:
```python
# Current: Branching based on string values
if retrieval_mode == "ann":
    # ...
elif retrieval_mode == "exact":
    # ...

# Better: ADTs eliminate branching
class ANNRetrieval(RetrievalStrategy): ...
class ExactRetrieval(RetrievalStrategy): ...

# No branching needed - polymorphism handles it
strategy.search(query)
```

#### Gap 5: **Insufficient Domain Modeling**

**Current**: Primitive obsession everywhere
- Strings for UUIDs, slugs, dates, URLs
- Dicts for commands, metadata, results
- Tuples for return values

**Should use**:
- **Value objects**: `AuthorUUID`, `PostSlug`, `EnrichmentKey`
- **Domain entities**: `Message`, `Post`, `Profile`, `Annotation`
- **Aggregates**: `Conversation`, `Period`, `Blog`
- **Domain services**: `AnonymizationService`, `EnrichmentService`

This would eliminate entire categories of complexity errors.

---

## Part 2: Industry-Standard Patterns

### Pattern 1: Parser Combinators for WhatsApp Parsing

**Replace** regex-based parser with **pyparsing** (already in stdlib ecosystem):

```python
# Modern approach: Declarative grammar
from pyparsing import (
    Combine, Group, Optional, ParseException, ParserElement,
    Regex, Suppress, Word, alphanums, nums, rest_of_line
)

# Grammar definition
date_part = Combine(Word(nums, max=2) + "/" + Word(nums, max=2) + "/" + Word(nums, min=2, max=4))
time_part = Combine(Word(nums, max=2) + ":" + Word(nums, exact=2))
ampm = Optional(Regex(r"[APap][Mm]"))
separator = Suppress(Regex(r"[—\-]"))
author = Regex(r"[^:]+")
message_text = rest_of_line

# Compose grammar
whatsapp_message = Group(
    Optional(date_part)("date") +
    Optional(Suppress(",") | Suppress(" ")) +
    time_part("time") +
    ampm("ampm") +
    separator +
    author("author") +
    Suppress(":") +
    message_text("message")
)

# Parse and validate in one step
class WhatsAppParser:
    def __init__(self, grammar: ParserElement):
        self.grammar = grammar

    def parse_line(self, line: str) -> Message | None:
        """Parse single line, return domain object or None."""
        try:
            result = self.grammar.parse_string(line)
            return Message.from_parse_result(result)  # Type-safe construction
        except ParseException:
            return None  # Continuation line
```

**Benefits**:
- **Declarative**: Grammar is self-documenting
- **Composable**: Reuse sub-grammars for different WhatsApp formats
- **Type-safe**: Direct mapping to domain objects
- **Testable**: Each grammar rule can be unit tested independently
- **Reduces complexity**: Eliminates `_LINE_PATTERN` regex and manual parsing logic

**Files to refactor**:
- `src/egregora/ingestion/parser.py` - Complete rewrite (500+ lines → ~200 lines)

### Pattern 2: Standard Pydantic-AI Agent Architecture

**Current issues**:
- Tool registration is imperative with nested conditionals (C901: 14)
- State is mutable with `list.append()`
- No proper dependency injection
- No use of `Result` types

**Standard pattern**:

```python
from pydantic_ai import Agent, RunContext, Tool
from pydantic import BaseModel, Field
from returns.result import Result, Success, Failure
from dataclasses import dataclass

# 1. Immutable state with proper types
@dataclass(frozen=True)
class WriterAgentDeps:
    """Immutable dependencies for writer agent."""
    config: WriterConfig
    paths: WriterPaths
    services: WriterServices

class WriterAgentState(BaseModel):
    """Tracked state during agent run."""
    saved_posts: frozenset[Path] = Field(default_factory=frozenset)
    saved_profiles: frozenset[Path] = Field(default_factory=frozenset)

    def with_post(self, path: Path) -> "WriterAgentState":
        """Immutable update - returns new state."""
        return self.model_copy(
            update={"saved_posts": self.saved_posts | {path}}
        )

# 2. Declarative tool registration with dependency injection
class WriterToolSet:
    """Tools for writer agent - dependency injection via constructor."""

    def __init__(self, deps: WriterAgentDeps):
        self.deps = deps

    @Tool
    def write_post(
        self,
        ctx: RunContext[WriterAgentState],
        metadata: PostMetadata,
        content: str
    ) -> Result[WritePostResult, str]:
        """Write post - returns Result type for error handling."""
        try:
            path = write_post(content, metadata.model_dump(), self.deps.paths.output_dir)
            # Immutable state update
            ctx.deps = ctx.deps.with_post(path)
            return Success(WritePostResult(status="success", path=str(path)))
        except OSError as e:
            return Failure(f"Failed to write post: {e}")

    @Tool
    def search_media(
        self,
        ctx: RunContext[WriterAgentState],
        query: str,
        **kwargs
    ) -> Result[SearchMediaResult, str]:
        """Search media with proper error handling."""
        try:
            results = self.deps.services.rag.search(
                RAGQuery(query_text=query, **kwargs)
            )
            return Success(SearchMediaResult.from_table(results))
        except VectorStoreError as e:
            return Failure(str(e))

# 3. Clean agent construction
def create_writer_agent(
    config: WriterConfig,
    paths: WriterPaths,
    services: WriterServices
) -> Agent[WriterAgentState, WriterAgentReturn]:
    """Factory for writer agent - all tools registered automatically."""
    deps = WriterAgentDeps(config=config, paths=paths, services=services)
    tools = WriterToolSet(deps)

    agent = Agent[WriterAgentState, WriterAgentReturn](
        model=config.model_name,
        deps_type=WriterAgentState,
        output_type=WriterAgentReturn
    )

    # Declarative registration - no conditionals!
    agent.tool(tools.write_post)
    agent.tool(tools.read_profile)
    agent.tool(tools.write_profile)

    if config.enable_rag:
        agent.tool(tools.search_media)

    if config.enable_banner:
        agent.tool(tools.generate_banner)

    return agent

# 4. Simple invocation
async def run_writer(
    config: WriterConfig,
    paths: WriterPaths,
    services: WriterServices,
    prompt: str
) -> Result[WriterAgentReturn, str]:
    """Run writer agent with Result type for error handling."""
    try:
        agent = create_writer_agent(config, paths, services)
        result = await agent.run(prompt)
        return Success(result.data)
    except Exception as e:
        logger.exception("Writer agent failed")
        return Failure(f"Agent error: {e}")
```

**Benefits**:
- **Immutability**: No mutable state bugs
- **Type safety**: Everything is properly typed
- **Error handling**: Result types instead of exceptions
- **Dependency injection**: Clean separation of concerns
- **Testability**: Easy to mock dependencies
- **Reduces complexity**: Eliminates nested conditionals (C901: 14 → 0)

### Pattern 3: Retrieval Strategy Pattern for RAG

**Current** (`store.py:436`): 77 statements, 21 complexity, 10 parameters
**Better**: Strategy + Pipeline patterns

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

# 1. Query object (from original plan - keep this!)
@dataclass(frozen=True)
class RAGQuery:
    """Immutable query specification."""
    query_text: str
    top_k: int = 10
    min_similarity: float = 0.7
    filters: RAGFilters = Field(default_factory=RAGFilters)
    strategy: RetrievalMode = RetrievalMode.ANN

# 2. Strategy protocol
class RetrievalStrategy(Protocol):
    """Interface for retrieval strategies."""

    def search(
        self,
        embedding: list[float],
        k: int
    ) -> Table:
        """Return top-k candidates."""
        ...

# 3. Concrete strategies
class ANNRetriever:
    """ANN search via DuckDB VSS."""

    def __init__(self, store: VectorStore, nprobe: int = 10):
        self.store = store
        self.nprobe = nprobe

    def search(self, embedding: list[float], k: int) -> Table:
        """ANN search with configurable nprobe."""
        return self.store._ann_search(embedding, k, self.nprobe)

class ExactRetriever:
    """Brute-force exact search."""

    def __init__(self, store: VectorStore):
        self.store = store

    def search(self, embedding: list[float], k: int) -> Table:
        """Exact cosine similarity search."""
        return self.store._exact_search(embedding, k)

# 4. Filter chain
class RAGFilter(ABC):
    """Base class for composable filters."""

    @abstractmethod
    def apply(self, results: Table) -> Table:
        """Filter results."""
        ...

class MediaTypeFilter(RAGFilter):
    def __init__(self, media_types: list[str]):
        self.media_types = media_types

    def apply(self, results: Table) -> Table:
        return results.filter(results.media_type.isin(self.media_types))

class DateRangeFilter(RAGFilter):
    def __init__(self, start: date, end: date):
        self.start = start
        self.end = end

    def apply(self, results: Table) -> Table:
        return results.filter(
            (results.date >= self.start) & (results.date <= self.end)
        )

class SimilarityThresholdFilter(RAGFilter):
    def __init__(self, min_similarity: float):
        self.min_similarity = min_similarity

    def apply(self, results: Table) -> Table:
        return results.filter(results.similarity >= self.min_similarity)

# 5. Search pipeline (replaces 77-statement function!)
class RAGSearchPipeline:
    """Composable search pipeline."""

    def __init__(
        self,
        store: VectorStore,
        embedding_service: EmbeddingService
    ):
        self.store = store
        self.embedding_service = embedding_service

    def search(self, query: RAGQuery) -> Result[Table, str]:
        """Execute search pipeline."""
        try:
            # Step 1: Embed query
            embedding = self.embedding_service.embed(query.query_text)

            # Step 2: Select retrieval strategy
            strategy = self._get_strategy(query.strategy)

            # Step 3: Retrieve candidates
            candidates = strategy.search(
                embedding,
                k=query.top_k * (query.filters.overfetch or 5)
            )

            # Step 4: Apply filter chain
            filtered = self._apply_filters(candidates, query.filters)

            # Step 5: Rank and limit
            results = (
                filtered
                .order_by(filtered.similarity.desc())
                .limit(query.top_k)
            )

            return Success(results)

        except VectorStoreError as e:
            return Failure(f"Search failed: {e}")

    def _get_strategy(self, mode: RetrievalMode) -> RetrievalStrategy:
        """Factory for retrieval strategies."""
        match mode:
            case RetrievalMode.ANN:
                return ANNRetriever(self.store)
            case RetrievalMode.EXACT:
                return ExactRetriever(self.store)
            case _:
                raise ValueError(f"Unknown mode: {mode}")

    def _apply_filters(self, table: Table, filters: RAGFilters) -> Table:
        """Apply filter chain."""
        result = table

        if filters.media_types:
            result = MediaTypeFilter(filters.media_types).apply(result)

        if filters.date_range:
            result = DateRangeFilter(*filters.date_range).apply(result)

        if filters.min_similarity:
            result = SimilarityThresholdFilter(filters.min_similarity).apply(result)

        return result
```

**Benefits**:
- **21 → 5 complexity**: Extracted methods, clear flow
- **77 → ~15 statements** per method
- **10 → 2 parameters** (query object + embedding service)
- **7 → 2 returns** (Success/Failure instead of early returns)
- **Extensible**: Add new strategies/filters without modifying existing code
- **Testable**: Each component can be tested independently

### Pattern 4: Domain-Driven Design with Value Objects

**Problem**: Primitive obsession leads to validation complexity

```python
# Current: Validation scattered everywhere
def write_post(content: str, metadata: dict, output_dir: Path) -> str:
    # Validate slug
    slug = metadata.get("slug")
    if not slug or not isinstance(slug, str):
        raise ValueError("Invalid slug")
    if not re.match(r"^[a-z0-9-]+$", slug):
        raise ValueError("Slug must be lowercase alphanumeric with hyphens")

    # Validate date
    date_str = metadata.get("date")
    if not date_str:
        raise ValueError("Missing date")
    try:
        post_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format")

    # ... more validation ...

    path = output_dir / "posts" / f"{slug}.md"
    path.write_text(content)
    return str(path)
```

**Better**: Value objects with built-in validation

```python
from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import NewType

# Domain primitives
class PostSlug(BaseModel):
    """Valid post slug (lowercase, alphanumeric + hyphens)."""
    value: str = Field(pattern=r"^[a-z0-9-]+$")

    def __str__(self) -> str:
        return self.value

class AuthorUUID(BaseModel):
    """Author identifier (validated UUID)."""
    value: str = Field(pattern=r"^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$")

    def __str__(self) -> str:
        return self.value

class EnrichmentKey(BaseModel):
    """Cache key for enrichments."""
    kind: Literal["url", "media"]
    identifier: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.identifier}"

# Domain entities
class PostMetadata(BaseModel):
    """Immutable post metadata with validation."""
    title: str = Field(min_length=1, max_length=200)
    slug: PostSlug
    date: date
    tags: frozenset[str] = Field(default_factory=frozenset)
    summary: str | None = Field(None, max_length=500)
    authors: frozenset[AuthorUUID] = Field(default_factory=frozenset)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("Title has leading/trailing whitespace")
        return v

class Post(BaseModel):
    """Complete post with content."""
    metadata: PostMetadata
    content: str = Field(min_length=1)
    path: Path | None = None

    def save(self, output_dir: Path) -> Path:
        """Save post to disk - no validation needed (already done)."""
        post_path = output_dir / "posts" / f"{self.metadata.slug}.md"
        post_path.parent.mkdir(parents=True, exist_ok=True)
        post_path.write_text(self._render())
        return post_path

    def _render(self) -> str:
        """Render post with frontmatter."""
        frontmatter = self.metadata.model_dump_json(indent=2)
        return f"---\n{frontmatter}\n---\n\n{self.content}"

# Now write_post is trivial!
def write_post(post: Post, output_dir: Path) -> Path:
    """Write post - validation already done by type system."""
    return post.save(output_dir)
```

**Benefits**:
- **No validation complexity**: Moved to type system
- **Impossible states impossible**: Can't have invalid slug in valid Post
- **Self-documenting**: Types describe domain precisely
- **Reduces branching**: No `if not slug or not isinstance(...)` checks
- **Composable**: Build complex entities from simple value objects

### Pattern 5: Algebraic Data Types for Branching Elimination

**Current**: String-based branching

```python
# 🔴 High cyclomatic complexity
def process_command(command: dict) -> None:
    cmd_type = command.get("command")
    target = command.get("target")
    value = command.get("value")

    if cmd_type == "set":
        if target == "alias":
            set_alias(value)
        elif target == "bio":
            set_bio(value)
        elif target == "avatar":
            set_avatar(value)
        # ... 10 more branches
    elif cmd_type == "remove":
        if target == "alias":
            remove_alias()
        elif target == "bio":
            remove_bio()
        # ... 10 more branches
    elif cmd_type == "opt-out":
        opt_out()
    elif cmd_type == "opt-in":
        opt_in()
```

**Better**: ADTs with pattern matching

```python
from enum import Enum
from dataclasses import dataclass
from typing import Literal

# ADT for commands
@dataclass(frozen=True)
class SetAlias:
    value: str

@dataclass(frozen=True)
class SetBio:
    value: str

@dataclass(frozen=True)
class SetAvatar:
    url_or_path: str

@dataclass(frozen=True)
class RemoveAlias:
    pass

@dataclass(frozen=True)
class RemoveBio:
    pass

@dataclass(frozen=True)
class OptOut:
    pass

@dataclass(frozen=True)
class OptIn:
    pass

# Union type
Command = SetAlias | SetBio | SetAvatar | RemoveAlias | RemoveBio | OptOut | OptIn

# Command handler using pattern matching (Python 3.10+)
def process_command(command: Command) -> Result[None, str]:
    """Process command - no branching needed, exhaustive match check."""
    match command:
        case SetAlias(value):
            return set_alias(value)
        case SetBio(value):
            return set_bio(value)
        case SetAvatar(url):
            return set_avatar(url)
        case RemoveAlias():
            return remove_alias()
        case RemoveBio():
            return remove_bio()
        case OptOut():
            return opt_out()
        case OptIn():
            return opt_in()
        case _:
            # Type checker ensures this is unreachable!
            raise AssertionError("Unreachable")

# Parser returns type-safe commands
def parse_egregora_command(message: str) -> Command | None:
    """Parse command - returns ADT instead of dict."""
    if message.lower() == "/egregora opt-out":
        return OptOut()
    if message.lower() == "/egregora opt-in":
        return OptIn()

    match = COMMAND_PATTERN.match(message)
    if not match:
        return None

    action = match.group(1).lower()
    args = match.group(2).strip()

    match (action, args.split(maxsplit=1)):
        case ("set", ["alias", value]):
            return SetAlias(value=value.strip("\"'"))
        case ("set", ["bio", value]):
            return SetBio(value=value.strip("\"'"))
        case ("set", ["avatar", url]):
            return SetAvatar(url_or_path=url.strip())
        case ("remove", ["alias"]):
            return RemoveAlias()
        case ("remove", ["bio"]):
            return RemoveBio()
        case _:
            return None
```

**Benefits**:
- **Type-safe**: Can't have invalid command states
- **Exhaustive**: Compiler checks all cases handled
- **No cyclomatic complexity**: Match is constant-time dispatch
- **Self-documenting**: All command types visible in union
- **Extensible**: Add new command = add new type to union

---

## Part 3: Improved Roadmap (8-10 Weeks)

### Phase 0: Setup & Infrastructure (Week 1)

**Goal**: Add modern tooling and dependencies

1. **Add dependencies**:
   ```toml
   [project.dependencies]
   # Already have these - great!
   "returns>=0.22.0"           # Result types ✅
   "pydantic-ai>=0.0.14"       # Agent framework ✅

   # Add these
   "pyparsing>=3.1.0"          # Parser combinators
   "result>=0.17.0"            # Alternative Result implementation
   ```

2. **Setup type checking**:
   - Enable strict mypy for new code
   - Add pyright config for exhaustiveness checking

3. **Create domain model skeleton**:
   - `src/egregora/domain/` - New package
   - `src/egregora/domain/value_objects.py` - PostSlug, AuthorUUID, etc.
   - `src/egregora/domain/entities.py` - Message, Post, Profile
   - `src/egregora/domain/commands.py` - Command ADTs

**Deliverable**: Infrastructure PR with new packages and types

---

### Phase 1: Domain Model (Week 2)

**Goal**: Implement value objects and entities

**Impact**: Eliminates validation complexity across codebase

1. **Implement value objects**:
   ```python
   # src/egregora/domain/value_objects.py
   - PostSlug (with validation)
   - AuthorUUID
   - MessageID
   - EnrichmentKey
   - Period (date range)
   ```

2. **Implement entities**:
   ```python
   # src/egregora/domain/entities.py
   - Message (parsed message with metadata)
   - Post (content + metadata)
   - Profile (author profile)
   - Annotation (conversation annotation)
   ```

3. **Implement commands ADT**:
   ```python
   # src/egregora/domain/commands.py
   - Command union type
   - All command variants
   - Pattern-matched dispatcher
   ```

4. **Add comprehensive tests**:
   - Unit tests for each value object
   - Property-based tests with hypothesis
   - Invalid input rejection tests

**Deliverable**: Domain model PR with 100% test coverage

**Files changed**: New files only (no refactoring yet)

---

### Phase 2: WhatsApp Parser Rewrite (Week 3-4)

**Goal**: Replace regex parser with pyparsing

**Impact**: Reduces C901: 15 → 0, PLR0912: 16 → 0 in parser.py

1. **Week 3: Grammar definition**:
   ```python
   # src/egregora/ingestion/grammar.py
   - WhatsApp message grammar (pyparsing)
   - Sub-grammars (date, time, author, etc.)
   - Multiple format support (US, EU, 12h, 24h)
   ```

2. **Week 3: Parser implementation**:
   ```python
   # src/egregora/ingestion/parser_v2.py
   - WhatsAppParser class
   - parse_line() → Message | None
   - parse_stream() → Iterator[Message]
   - Error recovery for malformed lines
   ```

3. **Week 4: Integration**:
   - Create adapter for old API
   - Run both parsers in parallel (validation)
   - Compare outputs with golden fixtures
   - Switch over when validated

4. **Week 4: Cleanup**:
   - Remove old parser code
   - Update tests
   - Remove regex patterns

**Deliverable**: Parser refactor PR

**Files changed**:
- `src/egregora/ingestion/parser.py` (500 lines → 200 lines)
- New `src/egregora/ingestion/grammar.py` (~150 lines)
- Tests updated

**Success metrics**:
- C901 errors: -1 (parse_multiple)
- PLR0912 errors: -1 (parse_multiple)
- PLR0911 errors: -1 (_resolve_message_date)
- Code maintainability: Significant improvement

---

### Phase 3: RAG Search Refactor (Week 5)

**Goal**: Strategy pattern + Pipeline for RAG

**Impact**: Reduces C901: 21 → 5, PLR0915: 77 → 15, PLR0911: 7 → 2, PLR0913: 10 → 2

1. **Create retrieval strategies**:
   ```python
   # src/egregora/agents/tools/rag/strategies.py
   - RetrievalStrategy protocol
   - ANNRetriever
   - ExactRetriever
   ```

2. **Create filter chain**:
   ```python
   # src/egregora/agents/tools/rag/filters.py
   - RAGFilter base class
   - MediaTypeFilter
   - DateRangeFilter
   - SimilarityThresholdFilter
   - AuthorFilter
   ```

3. **Implement search pipeline**:
   ```python
   # src/egregora/agents/tools/rag/pipeline.py
   - RAGSearchPipeline
   - Composable pipeline stages
   - Result type for error handling
   ```

4. **Refactor VectorStore.search()**:
   - Delegate to pipeline
   - Keep old API for backwards compatibility
   - Deprecate old parameters

5. **Update RAGQuery**:
   ```python
   # src/egregora/agents/tools/rag/query.py
   - Fluent builder API (from original plan)
   - Immutable query object
   - Type-safe parameters
   ```

**Deliverable**: RAG refactor PR

**Files changed**:
- `src/egregora/agents/tools/rag/store.py` (search: 77 → ~15 statements)
- New strategy/filter/pipeline files

**Success metrics**:
- C901: -1 (VectorStore.search)
- PLR0913: -1 (VectorStore.search)
- PLR0915: -1 (VectorStore.search)
- PLR0911: -1 (VectorStore.search)

---

### Phase 4: Agent Architecture Modernization (Week 6-7)

**Goal**: Standard Pydantic-AI patterns

**Impact**: Reduces C901: 14 → 0, PLR0913: 14 → 3, multiple files

#### Week 6: Writer Agent

1. **Create config objects** (from original plan):
   ```python
   # src/egregora/agents/writer/config.py
   - WriterConfig
   - WriterPaths
   - WriterServices (new)
   ```

2. **Refactor tool registration**:
   ```python
   # src/egregora/agents/writer/tools.py
   - WriterToolSet class
   - Dependency injection via constructor
   - Result types for error handling
   - Declarative registration
   ```

3. **Refactor agent state**:
   ```python
   # src/egregora/agents/writer/state.py
   - Immutable WriterAgentDeps
   - Immutable WriterAgentState
   - with_* methods for updates
   ```

4. **Refactor agent creation**:
   ```python
   # src/egregora/agents/writer/writer_agent.py
   - create_writer_agent() factory
   - Simplified run functions (3 params instead of 14)
   - Clean, linear flow
   ```

#### Week 7: Editor & Ranking Agents

5. **Apply same pattern to editor**:
   - `src/egregora/agents/editor/` - Same refactor
   - Reduces C901: 11 → 0
   - Reduces PLR0913: 6 → 3

6. **Apply same pattern to ranking**:
   - `src/egregora/agents/ranking/` - Same refactor
   - Reduces C901: 11 → 0 (load_profile)
   - Reduces PLR0913: 9 → 3

**Deliverable**: Agent modernization PR

**Files changed**:
- `src/egregora/agents/writer/writer_agent.py`
- `src/egregora/agents/editor/editor_agent.py`
- `src/egregora/agents/ranking/ranking_agent.py`
- All associated context/tools files

**Success metrics**:
- C901: -3 (_register_writer_tools, _register_editor_tools, load_profile)
- PLR0913: -5 (all agent functions)

---

### Phase 5: Enrichment & CLI (Week 8)

**Goal**: Pipeline decomposition + config objects

**Impact**: Reduces remaining C901, PLR0913, PLR0915 errors

1. **Enrichment decomposition**:
   ```python
   # src/egregora/enrichment/core.py
   - Extract _extract_urls_for_enrichment()
   - Extract _extract_media_for_enrichment()
   - Extract _enrich_urls_batch()
   - Extract _enrich_media_batch()
   - Extract _merge_enrichment_results()
   - Main enrich_table() becomes orchestrator (~20 lines)
   ```

2. **CLI decomposition**:
   ```python
   # src/egregora/cli.py
   - Extract _validate_process_config()
   - Extract _setup_pipeline_components()
   - Extract _run_pipeline()
   - Use config objects throughout
   ```

3. **Pipeline runner config**:
   ```python
   # src/egregora/pipeline/config.py
   - PipelineConfig
   - PipelinePaths
   - Replace 16-parameter run_source_pipeline()
   ```

**Deliverable**: Enrichment & CLI refactor PR

**Files changed**:
- `src/egregora/enrichment/core.py`
- `src/egregora/cli.py`
- `src/egregora/pipeline/runner.py`

**Success metrics**:
- C901: -3 (enrich_table, _validate_and_run_process, _register_ranking_cli)
- PLR0915: -3 (same functions)
- PLR0913: -2 (pipeline functions)

---

### Phase 6: Remaining Complexity (Week 9)

**Goal**: Fix remaining errors

1. **Avatar state machine**:
   - Implement AvatarProcessingState enum
   - Create AvatarStateMachine class
   - Refactor avatar functions
   - Reduces C901: 18 → 5 (3 functions)

2. **Profiler refactor**:
   - Extract command handlers
   - Use Command ADTs
   - Reduces C901: 11 → 0

3. **Adapter refactor**:
   - deliver_media with Result type
   - Reduces PLR0911: 7 → 2

4. **Misc cleanup**:
   - Apply config objects to remaining functions
   - Fix remaining PLR0913 errors

**Deliverable**: Final complexity PR

**Success metrics**: All 62 errors resolved

---

### Phase 7: Integration & Testing (Week 10)

**Goal**: Validate entire refactor

1. **Integration testing**:
   - Run full pipeline with golden fixtures
   - Compare outputs byte-for-byte
   - Performance benchmarks

2. **Type checking**:
   - Run mypy in strict mode
   - Run pyright for exhaustiveness checks
   - Fix any type errors

3. **Documentation**:
   - Update CLAUDE.md with new patterns
   - Add architecture decision records
   - Update contributor guide

4. **Cleanup**:
   - Remove deprecated code
   - Remove unused imports
   - Final ruff pass

**Deliverable**: Integration & docs PR

---

## Part 4: Risk Mitigation

### Risk 1: Parser Rewrite Breaking Compatibility

**Mitigation**:
- Run both parsers in parallel (Week 4)
- Compare outputs with assertions
- Keep old parser as fallback
- Gradual migration per-export

### Risk 2: Agent Refactor Breaking Tools

**Mitigation**:
- Comprehensive VCR test coverage
- Test each tool independently
- Gradual migration (writer → editor → ranking)
- Keep old API with deprecation warnings

### Risk 3: Performance Regression

**Mitigation**:
- Benchmark critical paths before refactor
- Profile after each phase
- Use caching appropriately
- Monitor pipeline execution time

### Risk 4: Type System Overhead

**Mitigation**:
- Use `frozen=True` for zero-cost abstractions
- Avoid runtime validation in hot paths
- Use NewType instead of classes where appropriate
- Profile and optimize if needed

### Risk 5: Scope Creep

**Mitigation**:
- Strict adherence to 10-week timeline
- Each phase is independently deliverable
- Can pause after any phase
- No "nice-to-have" features

---

## Part 5: Success Metrics

### Quantitative

| Metric | Before | Target | Improvement |
|--------|--------|--------|-------------|
| C901 violations | 20 | 0 | -100% |
| PLR0913 violations | 18 | 0 | -100% |
| PLR0915 violations | 14 | 0 | -100% |
| PLR0912 violations | 7 | 0 | -100% |
| PLR0911 violations | 3 | 0 | -100% |
| **Total errors** | **62** | **0** | **-100%** |
| Test coverage | ~85% | ≥90% | +5% |
| Type coverage (mypy) | ~60% | 95% | +35% |
| Avg function complexity | 8.5 | <5 | -41% |
| Avg function length | 35 lines | <20 lines | -43% |
| Avg parameters per function | 4.2 | <3 | -29% |

### Qualitative

1. **Maintainability**: Code is self-documenting with domain types
2. **Extensibility**: New features require minimal changes
3. **Type safety**: Invalid states impossible at compile time
4. **Testability**: Each component independently testable
5. **Modern patterns**: Aligned with industry standards
6. **Pydantic-AI best practices**: Standard agent architecture
7. **Error handling**: Result types instead of exceptions
8. **Parsing**: Declarative grammar instead of regex

---

## Part 6: Comparison with Original Plan

| Aspect | Original Plan | This Plan | Winner |
|--------|--------------|-----------|--------|
| **Timeline** | 6 weeks | 8-10 weeks | Original (faster) |
| **Scope** | Tactical fixes | Strategic refactor | This plan (better outcomes) |
| **Parser** | Visitor pattern | Complete rewrite with pyparsing | This plan |
| **Agent architecture** | Config objects | Full Pydantic-AI modernization | This plan |
| **Type system** | Minimal use | Extensive (ADTs, value objects) | This plan |
| **Error handling** | Exceptions | Result types | This plan |
| **Domain model** | Not addressed | Complete domain layer | This plan |
| **Long-term value** | Medium | High | This plan |
| **Risk** | Low | Medium | Original (safer) |
| **Learning curve** | Low | Medium | Original (easier) |

### Recommendation

**For production stability**: Original plan
**For long-term quality**: This plan
**Hybrid approach**:
1. Do Phases 0-2 from this plan (domain model + parser)
2. Do Phases 1-4 from original plan (config objects + tool registration)
3. Do Phases 3 + 5-6 from this plan (RAG + enrichment)

This gets you 80% of the benefits with 60% of the risk.

---

## Part 7: Next Steps

1. **Review this plan** with team
2. **Choose approach**: Original, This, or Hybrid
3. **Get stakeholder buy-in** for timeline
4. **Create GitHub project** with all phases
5. **Begin Phase 0** (setup)

**Estimated effort**:
- Original plan: ~120 hours (6 weeks × 20 hours)
- This plan: ~160-200 hours (8-10 weeks × 20 hours)
- Hybrid plan: ~140 hours (7 weeks × 20 hours)

---

## Conclusion

The original plan is solid for tactical complexity reduction. This plan goes further by:

1. ✅ **Modernizing the parser** with industry-standard tools (pyparsing)
2. ✅ **Leveraging Pydantic-AI** according to best practices
3. ✅ **Using the type system** to eliminate complexity at compile time
4. ✅ **Implementing domain-driven design** for better maintainability
5. ✅ **Using modern patterns** (ADTs, Result types, value objects)

**Bottom line**: Original plan fixes symptoms. This plan fixes root causes.

Choose based on your priorities:
- **Speed + low risk** → Original plan
- **Quality + long-term maintainability** → This plan
- **Balanced approach** → Hybrid plan

All three will successfully eliminate the 62 complexity errors. The difference is in *how* and *what you get beyond that*.
