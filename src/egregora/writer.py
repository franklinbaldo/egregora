"""Simple writer: LLM with write_post tool for editorial control."""

import logging
from pathlib import Path
import polars as pl
import yaml
from google import genai
from pydantic import BaseModel
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
    model: str = "gemini-2.0-flash-exp",
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
        model: Which LLM model to use
        enable_rag: Whether to use RAG for context

    Returns:
        Dict with 'posts' and 'profiles' lists of saved file paths
    """

    if df.is_empty():
        return {"posts": [], "profiles": []}

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

    # Build custom instructions section
    custom_instructions = ""
    if custom_writer_prompt:
        custom_instructions = f"""
## Custom Writing Instructions

{custom_writer_prompt}
"""

    prompt = f"""You are a blog editor reviewing WhatsApp group messages from {date}.
{custom_instructions}
{markdown_features_section}
Messages (anonymized, with enriched context):
{markdown_table}

Active authors in this period: {', '.join(active_authors)}
{profiles_context}
{rag_context}
Your job:
1. Analyze these messages
2. **Consider the participants' writing styles, interests, and expertise from their profiles**
3. Write posts that reflect the group's collective voice and intentions
4. Match the tone and style of the active participants
5. Reference and link to related previous posts when relevant
6. Update author profiles based on new contributions

BLOG POSTS:
Use write_post tool 0-N times:
- 0 times if it's all noise/spam
- 1 time for a single coherent daily summary
- Multiple times for distinct topics

When writing posts, consider participant profiles:
- Match the tone and style of the active participants
- Consider their areas of expertise and interests
- Reflect the group's collective voice and intentions
- Use profiles to understand conversation context
- Write content that aligns with their communication style

Examples:
- If profiles show technical interests → Write detailed technical posts
- If profiles show casual style → Write conversational posts
- If profiles show diverse expertise → Create multi-perspective posts

**CRITICAL - Author References in Post Content:**
- ALWAYS reference authors by their UUID (e.g., "Author a3f8c2b1 discussed...")
- NEVER use aliases or real names in post content
- Posts must be privacy-safe and immutable
- Aliases are for display/rendering only, not for storage

Example:
✅ "Author a3f8c2b1 shared insights about Python optimization..."
✅ "The discussion between b4e9d3c2 and c5f7e4d3 revealed..."
❌ "Franklin shared insights..." (NEVER use alias in content)
❌ "The discussion between Sarah and John..." (NEVER use alias in content)

For each post, provide:
- title: Engaging post title
- slug: URL-friendly slug (lowercase, hyphens)
- date: "{date}"
- tags: Relevant topic tags
- summary: 1-2 sentence summary
- authors: List of anonymized author IDs who contributed
- content: Full markdown post content

AUTHOR PROFILES:
After writing posts, update author profiles:
1. Use read_profile(author_uuid) to read current profile
2. Analyze author's contributions in this period
3. Use write_profile(author_uuid, content) to update profile

Profile format (markdown):
- Writing style and voice
- Topics of interest
- Expertise areas
- Communication patterns
- Notable contributions

Be editorial. Only write quality content. Skip trivial conversations.
"""

    tools = [
        {
            "name": "write_post",
            "description": "Save a blog post with metadata (CMS tool)",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Markdown post content"
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "slug": {"type": "string"},
                            "date": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "summary": {"type": "string"},
                            "authors": {"type": "array", "items": {"type": "string"}},
                            "category": {"type": "string"}
                        },
                        "required": ["title", "slug", "date"]
                    }
                },
                "required": ["content", "metadata"]
            }
        },
        {
            "name": "read_profile",
            "description": "Read the current profile for an author",
            "parameters": {
                "type": "object",
                "properties": {
                    "author_uuid": {
                        "type": "string",
                        "description": "The anonymized author UUID"
                    }
                },
                "required": ["author_uuid"]
            }
        },
        {
            "name": "write_profile",
            "description": "Write or update an author's profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "author_uuid": {
                        "type": "string",
                        "description": "The anonymized author UUID"
                    },
                    "content": {
                        "type": "string",
                        "description": "Profile content in markdown format"
                    }
                },
                "required": ["author_uuid", "content"]
            }
        }
    ]

    # Multi-turn conversation for tool calling
    messages = [{"role": "user", "parts": [{"text": prompt}]}]
    saved_posts = []
    saved_profiles = []
    max_turns = 10  # Prevent infinite loops

    for turn in range(max_turns):
        response = await client.aio.models.generate_content(
            model=model,
            contents=messages,
            config={
                "tools": tools,
                "temperature": 0.7,
            }
        )

        # Check if there are tool calls
        has_tool_calls = False
        tool_responses = []

        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                has_tool_calls = True
                fn_call = part.function_call
                fn_name = fn_call.name
                fn_args = fn_call.args

                # Execute the tool
                try:
                    if fn_name == "write_post":
                        content = fn_args.get("content", "")
                        metadata = fn_args.get("metadata", {})
                        path = write_post(content, metadata, output_dir)
                        saved_posts.append(path)
                        tool_responses.append({
                            "function_call": fn_call,
                            "function_response": {
                                "name": fn_name,
                                "response": {"status": "success", "path": path}
                            }
                        })

                    elif fn_name == "read_profile":
                        author_uuid = fn_args.get("author_uuid", "")
                        profile_content = read_profile(author_uuid, profiles_dir)
                        tool_responses.append({
                            "function_call": fn_call,
                            "function_response": {
                                "name": fn_name,
                                "response": {"content": profile_content or "No profile exists yet."}
                            }
                        })

                    elif fn_name == "write_profile":
                        author_uuid = fn_args.get("author_uuid", "")
                        content = fn_args.get("content", "")
                        path = write_profile(author_uuid, content, profiles_dir)
                        saved_profiles.append(path)
                        tool_responses.append({
                            "function_call": fn_call,
                            "function_response": {
                                "name": fn_name,
                                "response": {"status": "success", "path": path}
                            }
                        })

                except Exception as e:
                    tool_responses.append({
                        "function_call": fn_call,
                        "function_response": {
                            "name": fn_name,
                            "response": {"status": "error", "error": str(e)}
                        }
                    })

        # If no tool calls, we're done
        if not has_tool_calls:
            break

        # Add assistant response and tool responses to conversation
        messages.append({"role": "model", "parts": response.candidates[0].content.parts})

        for tool_resp in tool_responses:
            messages.append({
                "role": "user",
                "parts": [{
                    "function_response": tool_resp["function_response"]
                }]
            })

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
