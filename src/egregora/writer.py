"""Simple writer: LLM with write_post tool for editorial control."""

import logging
from functools import lru_cache
from pathlib import Path
import polars as pl
import yaml
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel
from .genai_utils import call_with_retries
from .write_post import write_post
from .profiler import read_profile, write_profile, get_active_authors
from .rag import VectorStore, query_similar_posts, index_post

logger = logging.getLogger(__name__)


class PostMetadata(BaseModel):
    """Metadata schema for write_post tool."""
    title: str
    slug: str
    date: str
    tags: list[str] = []
    summary: str = ""
    authors: list[str] = []
    category: str | None = None


@lru_cache(maxsize=1)
def _writer_tools() -> list[genai_types.Tool]:
    """Return tool definitions compatible with the google.genai SDK."""
    metadata_schema = genai_types.Schema(
        type=genai_types.Type.OBJECT,
        properties={
            "title": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Engaging post title",
            ),
            "slug": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="URL-friendly slug (lowercase, hyphenated)",
            ),
            "date": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Publication date YYYY-MM-DD",
            ),
            "tags": genai_types.Schema(
                type=genai_types.Type.ARRAY,
                description="Relevant topic tags",
                items=genai_types.Schema(type=genai_types.Type.STRING),
            ),
            "summary": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Short summary (1-2 sentences)",
            ),
            "authors": genai_types.Schema(
                type=genai_types.Type.ARRAY,
                description="List of anonymized author UUIDs",
                items=genai_types.Schema(type=genai_types.Type.STRING),
            ),
            "category": genai_types.Schema(
                type=genai_types.Type.STRING,
                description="Optional category slug",
                nullable=True,
            ),
        },
        required=["title", "slug", "date"],
    )

    write_post_decl = genai_types.FunctionDeclaration(
        name="write_post",
        description="Save a blog post with metadata (CMS tool)",
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "content": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Markdown post content",
                ),
                "metadata": metadata_schema,
            },
            required=["content", "metadata"],
        ),
    )

    read_profile_decl = genai_types.FunctionDeclaration(
        name="read_profile",
        description="Read the current profile for an author",
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "author_uuid": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="The anonymized author UUID",
                )
            },
            required=["author_uuid"],
        ),
    )

    write_profile_decl = genai_types.FunctionDeclaration(
        name="write_profile",
        description="Write or update an author's profile",
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "author_uuid": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="The anonymized author UUID",
                ),
                "content": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Profile content in markdown format",
                ),
            },
            required=["author_uuid", "content"],
        ),
    )

    return [
        genai_types.Tool(
            function_declarations=[
                write_post_decl,
                read_profile_decl,
                write_profile_decl,
            ]
        )
    ]


def load_site_config(output_dir: Path) -> dict:
    """
    Load egregora configuration from mkdocs.yml if it exists.

    Reads the `extra.egregora` section from mkdocs.yml in the output directory.
    Returns empty dict if no config found.

    Args:
        output_dir: Output directory (will look for mkdocs.yml in parent/root)

    Returns:
        Dict with egregora config (writer_prompt, rag settings, etc.)
    """
    # Try to find mkdocs.yml in parent directory (site root)
    mkdocs_path = output_dir.parent / "mkdocs.yml"

    # If not found, try in output_dir itself
    if not mkdocs_path.exists():
        mkdocs_path = output_dir / "mkdocs.yml"

    if not mkdocs_path.exists():
        logger.debug("No mkdocs.yml found, using default config")
        return {}

    try:
        config = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8"))
        egregora_config = config.get("extra", {}).get("egregora", {})
        logger.info(f"Loaded site config from {mkdocs_path}")
        return egregora_config
    except Exception as e:
        logger.warning(f"Could not load site config from {mkdocs_path}: {e}")
        return {}


def load_markdown_extensions(output_dir: Path) -> str:
    """
    Load markdown_extensions section from mkdocs.yml and format for LLM.

    The LLM understands these extension names and knows how to use them.
    We just pass the YAML config directly.

    Args:
        output_dir: Output directory (will look for mkdocs.yml in parent/root)

    Returns:
        Formatted YAML string with markdown_extensions section
    """
    # Try to find mkdocs.yml in parent directory (site root)
    mkdocs_path = output_dir.parent / "mkdocs.yml"

    # If not found, try in output_dir itself
    if not mkdocs_path.exists():
        mkdocs_path = output_dir / "mkdocs.yml"

    if not mkdocs_path.exists():
        logger.debug("No mkdocs.yml found, no custom markdown extensions")
        return ""

    try:
        config = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8"))
        extensions = config.get("markdown_extensions", [])

        if not extensions:
            return ""

        # Format as YAML for the LLM
        yaml_section = yaml.dump(
            {"markdown_extensions": extensions},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        logger.info(f"Loaded {len(extensions)} markdown extensions from {mkdocs_path}")
        return yaml_section

    except Exception as e:
        logger.warning(f"Could not load markdown extensions from {mkdocs_path}: {e}")
        return ""


def get_top_authors(df: pl.DataFrame, limit: int = 20) -> list[str]:
    """
    Get top N active authors by message count.

    Args:
        df: DataFrame with 'author' column
        limit: Max number of authors (default 20)

    Returns:
        List of author UUIDs (most active first)
    """
    # Filter out system and enrichment entries
    author_counts = (
        df
        .filter(pl.col("author").is_in(["system", "egregora"]).not_())
        .filter(pl.col("author").is_not_null())
        .filter(pl.col("author") != "")
        .group_by("author")
        .count()
        .sort("count", descending=True)
        .head(limit)
    )

    if author_counts.is_empty():
        return []

    return author_counts["author"].to_list()


async def write_posts_for_period(
    df: pl.DataFrame,
    date: str,
    client: genai.Client,
    output_dir: Path = Path("output/posts"),
    profiles_dir: Path = Path("output/profiles"),
    rag_dir: Path = Path("output/rag"),
    model_config=None,
    enable_rag: bool = True,
) -> dict[str, list[str]]:
    """
    Let LLM analyze period's messages, write 0-N posts, and update author profiles.

    The LLM has full editorial control via tools:
    - write_post: Create blog posts with metadata
    - read_profile: Read existing author profiles
    - write_profile: Update author profiles

    RAG system provides context from previous posts for continuity.

    Args:
        df: DataFrame with messages for the period (already enriched)
        date: Period identifier (e.g., "2025-01-01")
        client: Gemini client
        output_dir: Where to save posts
        profiles_dir: Where to save author profiles
        rag_dir: Where RAG vector store is saved
        model_config: Model configuration object (contains model selection logic)
        enable_rag: Whether to use RAG for context

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths
    """
    from .model_config import ModelConfig

    if df.is_empty():
        return {"posts": [], "profiles": []}

    # Get model name from config
    if model_config is None:
        model_config = ModelConfig()  # Use defaults
    model = model_config.get_model("writer")

    # Get active authors for profiling context
    active_authors = get_active_authors(df)

    markdown_table = df.write_csv(separator="|")

    # Query RAG for similar previous posts (for continuity)
    rag_context = ""
    if enable_rag:
        try:
            store = VectorStore(rag_dir / "chunks.parquet")
            similar_posts = await query_similar_posts(
                df, client, store, top_k=5, deduplicate=True
            )

            if not similar_posts.is_empty():
                logger.info(f"Found {len(similar_posts)} similar previous posts")
                rag_context = "\n\n## Related Previous Posts (for continuity and linking):\n"
                rag_context += "You can reference these posts in your writing to maintain conversation continuity.\n\n"

                for row in similar_posts.iter_rows(named=True):
                    rag_context += f"### [{row['post_title']}] ({row['post_date']})\n"
                    rag_context += f"{row['content'][:400]}...\n"
                    rag_context += f"- Tags: {', '.join(row['tags']) if row['tags'] else 'none'}\n"
                    rag_context += f"- Similarity: {row['similarity']:.2f}\n\n"
            else:
                logger.info("No similar previous posts found")
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")

    # Load profiles for top active authors (for style/context awareness)
    profiles_context = ""
    top_authors = get_top_authors(df, limit=20)

    if top_authors:
        logger.info(f"Loading profiles for {len(top_authors)} active authors")
        profiles_context = "\n\n## Active Participants (Profiles):\n"
        profiles_context += "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n"

        for author_uuid in top_authors:
            profile_content = read_profile(author_uuid, profiles_dir)

            if profile_content:
                profiles_context += f"### Author: {author_uuid}\n"
                profiles_context += f"{profile_content}\n\n"
            else:
                # No profile yet (first time seeing this author)
                profiles_context += f"### Author: {author_uuid}\n"
                profiles_context += "(No profile yet - first appearance)\n\n"

        logger.info(f"Profiles context: {len(profiles_context)} characters")

    # Load site configuration from mkdocs.yml
    site_config = load_site_config(output_dir)
    custom_writer_prompt = site_config.get("writer_prompt", "")

    # Load markdown extensions from mkdocs.yml
    markdown_extensions_yaml = load_markdown_extensions(output_dir)

    # Build markdown features section for prompt
    markdown_features_section = ""
    if markdown_extensions_yaml:
        markdown_features_section = f"""
## Available Markdown Features

This MkDocs site has the following extensions configured:

```yaml
{markdown_extensions_yaml}```

Use these features appropriately in your posts. You understand how each extension works.
"""

    # Render prompt from Jinja template
    from .prompt_templates import render_writer_prompt

    prompt = render_writer_prompt(
        date=date,
        markdown_table=markdown_table,
        active_authors=', '.join(active_authors),
        custom_instructions=custom_writer_prompt or "",
        markdown_features=markdown_features_section,
        profiles_context=profiles_context,
        rag_context=rag_context,
    )

    config = genai_types.GenerateContentConfig(
        tools=_writer_tools(),
        temperature=0.7,
    )

    messages: list[genai_types.Content] = [
        genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
    ]
    saved_posts: list[str] = []
    saved_profiles: list[str] = []
    max_turns = 10  # Prevent infinite loops

    for _ in range(max_turns):
        try:
            response = await call_with_retries(
                client.aio.models.generate_content,
                model=model,
                contents=messages,
                config=config,
            )
        except Exception as exc:
            logger.error("Writer generation failed: %s", exc)
            raise

        # Check if there are tool calls
        has_tool_calls = False
        tool_responses: list[genai_types.Content] = []

        # Defensive checks for response structure
        if not response or not response.candidates:
            logger.warning("No candidates in response, ending conversation")
            break

        candidate = response.candidates[0]
        if not candidate or not candidate.content or not candidate.content.parts:
            logger.warning("No content parts in response, ending conversation")
            break

        for part in candidate.content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                has_tool_calls = True
                fn_call = part.function_call
                fn_name = fn_call.name
                fn_args = fn_call.args or {}

                # Execute the tool
                try:
                    if fn_name == "write_post":
                        content = fn_args.get("content", "")
                        metadata = fn_args.get("metadata", {})
                        path = write_post(content, metadata, output_dir)
                        saved_posts.append(path)
                        tool_responses.append(
                            genai_types.Content(
                                role="user",
                                parts=[
                                    genai_types.Part(
                                        function_response=genai_types.FunctionResponse(
                                            id=getattr(fn_call, "id", None),
                                            name=fn_name,
                                            response={"status": "success", "path": path},
                                        )
                                    )
                                ],
                            )
                        )

                    elif fn_name == "read_profile":
                        author_uuid = fn_args.get("author_uuid", "")
                        profile_content = read_profile(author_uuid, profiles_dir)
                        tool_responses.append(
                            genai_types.Content(
                                role="user",
                                parts=[
                                    genai_types.Part(
                                        function_response=genai_types.FunctionResponse(
                                            id=getattr(fn_call, "id", None),
                                            name=fn_name,
                                            response={
                                                "content": profile_content
                                                or "No profile exists yet."
                                            },
                                        )
                                    )
                                ],
                            )
                        )

                    elif fn_name == "write_profile":
                        author_uuid = fn_args.get("author_uuid", "")
                        content = fn_args.get("content", "")
                        path = write_profile(author_uuid, content, profiles_dir)
                        saved_profiles.append(path)
                        tool_responses.append(
                            genai_types.Content(
                                role="user",
                                parts=[
                                    genai_types.Part(
                                        function_response=genai_types.FunctionResponse(
                                            id=getattr(fn_call, "id", None),
                                            name=fn_name,
                                            response={"status": "success", "path": path},
                                        )
                                    )
                                ],
                            )
                        )

                except Exception as e:
                    tool_responses.append(
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part(
                                    function_response=genai_types.FunctionResponse(
                                        id=getattr(fn_call, "id", None),
                                        name=fn_name,
                                        response={"status": "error", "error": str(e)},
                                    )
                                )
                            ],
                        )
                    )

        # If no tool calls, we're done
        if not has_tool_calls:
            break

        # Add assistant response and tool responses to conversation
        messages.append(candidate.content)
        messages.extend(tool_responses)

    # Index newly created posts in RAG
    if enable_rag and saved_posts:
        try:
            store = VectorStore(rag_dir / "chunks.parquet")
            for post_path in saved_posts:
                await index_post(Path(post_path), client, store)
            logger.info(f"Indexed {len(saved_posts)} new posts in RAG")
        except Exception as e:
            logger.error(f"Failed to index posts in RAG: {e}")

    return {"posts": saved_posts, "profiles": saved_profiles}
