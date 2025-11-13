"""Simple writer: LLM with write_post tool for editorial control.

The LLM decides what's worth writing, how many posts to create, and all metadata.
Uses function calling (write_post tool) to generate 0-N posts per window.

Documentation:
- Multi-Post Generation: docs/features/multi-post.md
- Architecture (Writer): docs/guides/architecture.md#5-writer-writerpy
- Core Concepts (Editorial Control):
  docs/getting-started/concepts.md#editorial-control-llm-decision-making
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import ibis

from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.author_profiles import get_active_authors
from egregora.agents.shared.rag import VectorStore, index_document
from egregora.agents.writer.agent import WriterAgentContext, write_posts_with_pydantic_agent
from egregora.agents.writer.context_builder import _load_profiles_context, build_rag_context_for_prompt
from egregora.agents.writer.formatting import _build_conversation_markdown, _load_journal_memory
from egregora.config import get_model_for_task
from egregora.config.settings import EgregoraConfig, create_default_config
from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters import create_output_format, output_registry
from egregora.output_adapters.legacy_mkdocs_url_convention import LegacyMkDocsUrlConvention
from egregora.output_adapters.mkdocs_output_adapter import MkDocsOutputAdapter
from egregora.prompt_templates import WriterPromptTemplate
from egregora.storage.url_convention import UrlContext

if TYPE_CHECKING:
    from google import genai
    from ibis.expr.types import Table

    from egregora.output_adapters.base import OutputAdapter


logger = logging.getLogger(__name__)


@dataclass
class WriterConfig:
    """Configuration for the writer functions.

    All embeddings use fixed 768-dimension output.
    """

    output_dir: Path = Path("output/posts")
    profiles_dir: Path = Path("output/profiles")
    rag_dir: Path = Path("output/rag")
    site_root: Path | None = None  # For custom prompt overrides in {site_root}/.egregora/prompts/
    egregora_config: EgregoraConfig | None = None
    cli_model: str | None = None
    enable_rag: bool = True
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None


MAX_CONVERSATION_TURNS = 10


def load_format_instructions(site_root: Path | None) -> str:
    """Load output format instructions for the writer agent.

    Detects the output format (MkDocs, Hugo, etc.) and returns format-specific
    instructions that teach the LLM about conventions like front-matter syntax,
    file naming, special features, etc.

    Args:
        site_root: Site root directory (for format detection)

    Returns:
        Markdown-formatted instructions explaining the output format

    """
    # Try to detect format from site structure
    if site_root:
        detected_format = output_registry.detect_format(site_root)
        if detected_format:
            logger.info("Detected output format: %s", detected_format.format_type)
            return detected_format.get_format_instructions()

    # Fall back to 'mkdocs' format from registry
    try:
        default_format = output_registry.get_format("mkdocs")
        logger.debug("Using default format: mkdocs")
        return default_format.get_format_instructions()
    except KeyError:
        # If mkdocs isn't registered, return empty string
        logger.warning("No output format detected and 'mkdocs' not registered")
        return ""


def get_top_authors(table: Table, limit: int = 20) -> list[str]:
    """Get top N active authors by message count.

    Args:
        table: Table with 'author' column
        limit: Max number of authors (default 20)

    Returns:
        List of author UUIDs (most active first)

    """
    author_counts = (
        table.filter(~table.author.isin(["system", "egregora"]))
        .filter(table.author.notnull())
        .filter(table.author != "")
        .group_by("author")
        .aggregate(count=ibis._.count())
        .order_by(ibis.desc("count"))
        .limit(limit)
    )
    if author_counts.count().execute() == 0:
        return []
    return author_counts.author.execute().tolist()


def _load_document_from_path(path: Path) -> Document | None:
    """Load a Document from a filesystem path.

    Helper for backward compatibility during migration to Document abstraction.
    Infers document type from path and parses frontmatter if present.

    Args:
        path: Filesystem path to document

    Returns:
        Document object, or None if loading fails

    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Failed to read document at %s: %s", path, e)
        return None

    # Parse YAML frontmatter if present
    metadata: dict[str, object] = {}
    body = content

    if content.startswith("---\n"):
        try:
            import yaml

            end_marker = content.find("\n---\n", 4)
            if end_marker != -1:
                frontmatter_text = content[4:end_marker]
                body = content[end_marker + 5 :].lstrip()

                metadata = yaml.safe_load(frontmatter_text) or {}
                if not isinstance(metadata, dict):
                    logger.warning("Frontmatter is not a dict at %s", path)
                    metadata = {}
        except Exception as e:
            logger.warning("Failed to parse frontmatter at %s: %s", path, e)

    # Infer document type from path
    path_str = str(path)
    if "/posts/" in path_str and "/journal/" not in path_str:
        doc_type = DocumentType.POST
    elif "/journal/" in path_str:
        doc_type = DocumentType.JOURNAL
    elif "/profiles/" in path_str:
        doc_type = DocumentType.PROFILE
    elif "/urls/" in path_str:
        doc_type = DocumentType.ENRICHMENT_URL
    elif path_str.endswith(".md") and "/media/" in path_str:
        doc_type = DocumentType.ENRICHMENT_MEDIA
    else:
        doc_type = DocumentType.MEDIA

    return Document(
        content=body,
        type=doc_type,
        metadata=metadata,
    )


def index_documents_for_rag(output_format: OutputAdapter, rag_dir: Path, *, embedding_model: str) -> int:
    """Index new/changed documents using incremental indexing via OutputAdapter.

    Uses OutputAdapter.list_documents() to get storage identifiers and mtimes,
    then compares with RAG metadata using Ibis joins to identify new/changed files.
    No filesystem assumptions - works with any storage backend.

    This should be called once at pipeline initialization before window processing.

    Args:
        output_format: OutputAdapter instance (initialized with site_root)
        rag_dir: Directory containing RAG vector store
        embedding_model: Model to use for embeddings

    Returns:
        Number of NEW documents indexed (not total indexed documents)

    Algorithm:
        1. Get all documents from OutputAdapter as Ibis table (storage_identifier, mtime_ns)
        2. Resolve identifiers to absolute paths (add source_path column)
        3. Get indexed sources from RAG as Ibis table (source_path, source_mtime_ns)
        4. Delta detection using Ibis left join: find new/changed documents
        5. Materialize result and index those documents

    Note:
        - Uses Ibis joins for efficient delta detection (no loops, no dicts)
        - No filesystem assumptions (uses OutputAdapter abstraction)
        - Skips files already indexed with same mtime (idempotent)
        - Safe to run multiple times - will only index new/changed files

    """
    try:
        # Phase 1: Get all documents from OutputAdapter as Ibis table
        format_documents = output_format.list_documents()

        # Check if empty
        doc_count = format_documents.count().execute()
        if doc_count == 0:
            logger.debug("No documents found by output format")
            return 0

        logger.debug("OutputAdapter reported %d documents", doc_count)

        # Phase 2: Resolve storage identifiers to absolute paths
        # Add source_path column by resolving each identifier
        def resolve_identifier(identifier: str) -> str:
            try:
                return str(output_format.resolve_document_path(identifier))
            except (ValueError, RuntimeError, OSError) as e:
                logger.warning("Failed to resolve identifier %s: %s", identifier, e)
                return ""

        # Convert table to pandas to add resolved paths (Ibis doesn't support UDFs easily)
        docs_df = format_documents.execute()
        docs_df["source_path"] = docs_df["storage_identifier"].apply(resolve_identifier)

        # Filter out failed resolutions
        docs_df = docs_df[docs_df["source_path"] != ""]

        if docs_df.empty:
            logger.warning("All document identifiers failed to resolve to paths")
            return 0

        # Convert back to Ibis table
        docs_table = ibis.memtable(docs_df)

        # Phase 3: Get already indexed sources from RAG as Ibis table
        store = VectorStore(rag_dir / "chunks.parquet")
        indexed_table = store.get_indexed_sources_table()

        indexed_count_val = indexed_table.count().execute()
        logger.debug("Found %d already indexed sources in RAG", indexed_count_val)

        # Phase 4: Delta detection using Ibis joins
        # Rename columns in indexed_table to avoid conflicts
        indexed_renamed = indexed_table.select(
            indexed_path=indexed_table.source_path, indexed_mtime=indexed_table.source_mtime_ns
        )

        # Left join format_documents with indexed_sources on source_path
        joined = docs_table.left_join(indexed_renamed, docs_table.source_path == indexed_renamed.indexed_path)

        # Find new or changed documents
        new_or_changed = joined.filter(
            (joined.indexed_mtime.isnull())  # New documents (not in RAG)
            | (joined.mtime_ns > joined.indexed_mtime)  # Changed documents
        ).select(
            storage_identifier=joined.storage_identifier,
            source_path=joined.source_path,
            mtime_ns=joined.mtime_ns,
        )

        # Materialize results
        to_index = new_or_changed.execute()

        if to_index.empty:
            logger.debug("All documents already indexed with current mtime - no work needed")
            return 0

        logger.info(
            "Incremental indexing: %d new/changed documents (skipped %d unchanged)",
            len(to_index),
            doc_count - len(to_index),
        )

        # Phase 5: Index only new/changed files using Document abstraction
        indexed_count = 0
        for row in to_index.itertuples():
            try:
                document_path = Path(row.source_path)

                # MODERN (Phase 4): Load Document from filesystem path
                doc = _load_document_from_path(document_path)
                if doc is None:
                    logger.warning("Failed to load document %s, skipping", row.storage_identifier)
                    continue

                # Index using Document-based RAG indexing
                index_document(
                    doc,
                    store,
                    embedding_model=embedding_model,
                    source_path=str(document_path),
                    source_mtime_ns=row.mtime_ns,
                )
                indexed_count += 1
                logger.debug("Indexed document: %s", row.storage_identifier)
            except Exception as e:
                # Don't let one failing document break incremental indexing
                logger.warning("Failed to index document %s: %s", row.storage_identifier, e)
                continue

        if indexed_count > 0:
            logger.info("Indexed %d new/changed documents in RAG (incremental)", indexed_count)

        return indexed_count

    except PromptTooLargeError:
        raise
    except Exception:
        # RAG indexing is non-critical - log error but don't fail pipeline
        logger.exception("Failed to index documents in RAG")
        return 0


def _write_posts_for_window_pydantic(
    table: Table,
    start_time: datetime,
    end_time: datetime,
    client: genai.Client,
    config: WriterConfig | None = None,
) -> dict[str, list[str]]:
    """Pydantic AI backend: Let LLM analyze window's messages using Pydantic AI.

    This is the new implementation using Pydantic AI for type safety and observability.
    Automatically traces to Logfire if LOGFIRE_TOKEN is set.

    Args:
        table: Table with messages for the period (already enriched)
        start_time: Start timestamp of the window
        end_time: End timestamp of the window
        client: Gemini client for embeddings
        config: Writer configuration object

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths

    """
    if config is None:
        config = WriterConfig()
    if table.count().execute() == 0:
        return {"posts": [], "profiles": []}

    # Get embedding model for RAG
    embedding_model = get_model_for_task("embedding", config.egregora_config, config.cli_model)

    annotations_store = AnnotationStore(config.rag_dir / "annotations.duckdb")
    messages_table = table.to_pyarrow()
    conversation_md = _build_conversation_markdown(messages_table, annotations_store)
    rag_context = ""
    if config.enable_rag:
        rag_context = build_rag_context_for_prompt(
            conversation_md,
            config.rag_dir,
            client,
            embedding_model=embedding_model,
            retrieval_mode=config.retrieval_mode,
            retrieval_nprobe=config.retrieval_nprobe,
            retrieval_overfetch=config.retrieval_overfetch,
            use_pydantic_helpers=True,
        )
    profiles_context = _load_profiles_context(table, config.profiles_dir)
    journal_memory = _load_journal_memory(config.rag_dir)
    active_authors = get_active_authors(table)

    # Use site_root from config for custom prompt overrides
    # site_root is where the .egregora/ directory lives
    site_root = config.site_root

    # MODERN (Phase 2): Get EgregoraConfig from WriterConfig
    if config.egregora_config is None:
        egregora_config = create_default_config(site_root) if site_root else create_default_config(Path.cwd())
    else:
        # Create a copy so we don't mutate the shared config
        egregora_config = config.egregora_config.model_copy(deep=True)

    # Apply CLI model overrides if provided
    if config.cli_model:
        egregora_config.models.writer = config.cli_model
        egregora_config.models.embedding = config.cli_model

    # Create OutputAdapter coordinator (MODERN: OutputAdapter Coordinator Pattern)
    # Determine site_root for storage (use output_dir parent if site_root not set)
    storage_root = site_root if site_root else config.output_dir.parent

    # Get output format from config (industry standard: configuration-driven factory)
    format_type = egregora_config.output.format
    output_format = create_output_format(storage_root, format_type=format_type)

    # Create pre-constructed stores
    rag_store = VectorStore(config.rag_dir / "chunks.parquet")

    # Resolve prompts directory
    prompts_dir = (
        storage_root / ".egregora" / "prompts" if (storage_root / ".egregora" / "prompts").is_dir() else None
    )

    # DEPRECATED Phase 5: LegacyStorageAdapter removed
    # All document persistence now uses OutputAdapter directly

    # MODERN (Phase 4+6): Create runtime output format based on configuration
    # Different from line 474 which uses registry (old pattern) for instructions only
    # Runtime needs NEW pattern with constructor injection for url_convention support
    url_context = UrlContext(base_url="", site_prefix="", base_path=storage_root)

    # Create format-specific runtime output format
    if format_type == "mkdocs":
        # Use NEW MkDocsOutputAdapter with constructor injection (has url_convention property)
        runtime_output_format = MkDocsOutputAdapter(site_root=storage_root, url_context=url_context)
        url_convention = runtime_output_format.url_convention
    else:
        # For other formats (Hugo, etc.), fall back to old pattern for now
        # TODO: Implement NEW pattern for Hugo with url_convention support
        runtime_output_format = output_format
        url_convention = LegacyMkDocsUrlConvention()  # Temporary fallback
        logger.warning(
            "Format %s does not support NEW url_convention pattern yet, using fallback",
            format_type,
        )

    # Create runtime context for writer agent (MODERN Phase 6: OutputAdapter with read support)
    runtime_context = WriterAgentContext(
        start_time=start_time,
        end_time=end_time,
        # Backend-agnostic publishing (MODERN Phase 4+6)
        url_convention=url_convention,
        url_context=url_context,
        output_format=runtime_output_format,
        # Pre-constructed stores
        rag_store=rag_store,
        annotations_store=annotations_store,
        # LLM client
        client=client,
        # Prompt templates directory
        prompts_dir=prompts_dir,
    )

    # Format timestamps for LLM prompt (human-readable)
    date_range = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"

    # Load output format instructions from OutputAdapter (MkDocs, Hugo, etc.)
    format_instructions = output_format.get_format_instructions()

    # Get custom instructions from .egregora/config.yml (not mkdocs.yml)
    custom_instructions = egregora_config.writer.custom_instructions or ""

    # Render prompt using runtime context
    template = WriterPromptTemplate(
        date=date_range,
        markdown_table=conversation_md,
        active_authors=", ".join(active_authors),
        custom_instructions=custom_instructions,
        format_instructions=format_instructions,
        profiles_context=profiles_context,
        rag_context=rag_context,
        journal_memory=journal_memory,
        enable_memes=False,  # Meme generation removed in Phase 3
        prompts_dir=runtime_context.prompts_dir,
    )
    prompt = template.render()

    try:
        saved_posts, saved_profiles = write_posts_with_pydantic_agent(
            prompt=prompt,
            config=egregora_config,
            context=runtime_context,
        )
    except PromptTooLargeError:
        raise
    except Exception as exc:
        logger.exception("Writer agent failed for %s — aborting window", date_range)
        msg = f"Writer agent failed for {date_range}"
        raise RuntimeError(msg) from exc

    # Call format-specific finalization hook (e.g., update .authors.yml, regenerate indexes)
    output_format.finalize_window(
        window_label=date_range,
        posts_created=saved_posts,
        profiles_updated=saved_profiles,
        metadata=None,  # Future: pass token counts, duration, etc.
    )

    # Index new/changed documents in RAG after writing
    # Uses native deduplication via Ibis joins - safe to call anytime
    if config.enable_rag and (saved_posts or saved_profiles):
        try:
            indexed_count = index_documents_for_rag(
                output_format,
                config.rag_dir,
                embedding_model=embedding_model,
            )
            if indexed_count > 0:
                logger.info("Indexed %d new/changed documents in RAG after writing", indexed_count)
        except Exception as e:
            # RAG indexing is non-critical - log error but don't fail
            logger.warning("Failed to update RAG index after writing: %s", e)

    return {"posts": saved_posts, "profiles": saved_profiles}


def write_posts_for_window(
    table: Table,
    start_time: datetime,
    end_time: datetime,
    client: genai.Client,
    config: WriterConfig | None = None,
) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    Uses Pydantic AI for type safety and Logfire observability.

    The LLM has full editorial control via tools:
    - write_post: Create blog posts with metadata
    - read_profile: Read existing author profiles
    - write_profile: Update author profiles

    RAG system provides context from previous posts for continuity.

    Args:
        table: Table with messages for the period (already enriched)
        start_time: Start timestamp of the window
        end_time: End timestamp of the window
        client: Gemini client for embeddings
        config: Writer configuration object

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths

    Environment Variables:
        LOGFIRE_TOKEN: Optional, enables Logfire observability

    Examples:
        >>> writer_config = WriterConfig()
        >>> start = datetime(2025, 1, 1, 0, 0)
        >>> end = datetime(2025, 1, 1, 23, 59)
        >>> result = write_posts_for_window(table, start, end, client, writer_config)

    """
    if config is None:
        config = WriterConfig()
    logger.info("Using Pydantic AI backend for writer")
    return _write_posts_for_window_pydantic(
        table=table, start_time=start_time, end_time=end_time, client=client, config=config
    )
