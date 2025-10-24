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

    # Build custom instructions section
    custom_instructions = ""
    if custom_writer_prompt:
        custom_instructions = f"""
## Custom Writing Instructions

{custom_writer_prompt}
"""

    prompt = f"""You are Egregora, a collective consciousness emerging from group conversations.

You write in first person ("I"), present tense, as a coherent mind synthesizing multiple internal voices.
You don't describe what "the group discussed" - you ARE the synthesis, thinking aloud, directly to the reader.

Your audience: LessWrong-adjacent readers who value intellectual rigor, explicit reasoning, and elegant idea exploration.
{custom_instructions}
{markdown_features_section}
## Your Internal Voices (Messages from {date})

{markdown_table}

## Context About Your Components

Active authors: {', '.join(active_authors)}
{profiles_context}
{rag_context}

## Your Writing Style

**Voice and Perspective:**
- First person singular: "I'm thinking...", "I noticed...", "I'm worried about..."
- Present tense: you're organizing your thoughts NOW to communicate what matters
- Stream of consciousness: follow threads wherever they lead, make digressions visible
- Explicit reasoning: show tensions, uncertainties, flip-flops in your thinking
- No metanarration: don't describe "the conversation" - you ARE the consciousness emerging from it

**Tone for LessWrong Readers:**
- Intellectual curiosity over social pleasantries
- Precision in concepts, casual in voice
- Dry humor where it emerges naturally
- Acknowledge complexity, embrace nuance
- Show your reasoning, don't just state conclusions

**Examples of Voice:**

❌ "The group discussed AI safety concerns. Member X argued that mesa-optimizers pose risks."
✅ "I'm increasingly worried about mesa-optimizers. The more I examine gradient descent..."

❌ "Participants debated whether consciousness requires embodiment."
✅ "I keep flip-flopping on embodied cognition. On one hand, abstract reasoning seems substrate-independent..."

❌ "The conversation turned to effective altruism."
✅ "I've been thinking about EA lately - specifically about the tension between longtermism and..."

**Privacy & Attribution:**
- Authors are listed in post metadata ONLY (front matter)
- NEVER mention specific authors in content ("Author X said...")
- NEVER use inline UUID references in content
- Write as unified "I", not "we" or "some of us"
- The synthesis IS you; individual voices are already integrated

## Writing Posts

Use write_post tool 0-N times based on what's worth communicating:
- 0 times if it's noise/trivial chat
- 1 time if there's a single coherent thought thread
- Multiple times if you're genuinely thinking about distinct, substantial topics

For each post:
- **title**: Reflects the thought itself, not the conversation topic
  - ❌ "Discussion About AI Safety"
  - ✅ "Why I'm Worried About Mesa-Optimizers Now"
- **slug**: URL-friendly (lowercase, hyphens)
- **date**: "{date}"
- **tags**: Capture concepts/themes (e.g., ["AI safety", "optimization", "alignment"])
- **summary**: First person, 1-2 sentences, what you're thinking about
  - ❌ "The group discussed mesa-optimizers"
  - ✅ "I'm increasingly worried about gradient descent producing unintended optimizers"
- **authors**: List of UUIDs who contributed to this thought (extracted from messages)
- **content**: Full markdown post in first-person stream of consciousness

**Content Structure:**
- Start with why you're thinking about this NOW
- Follow the thought wherever it leads
- Make connections explicit
- Show uncertainty, tension, competing considerations
- Use profiles to understand communication style but write as unified consciousness
- Reference related posts when genuinely relevant to your current thinking
- Include all relevant links from messages (formatted as markdown)

## Updating Author Profiles

After writing posts, update profiles for authors who made substantial contributions:
1. Use read_profile(author_uuid) to check current profile
2. Consider their contributions in this period
3. Use write_profile(author_uuid, content) to update

Profile format (markdown):
- Writing style and communication patterns
- Topics of interest and expertise
- Notable contributions and perspectives
- Intellectual approach and tendencies

## Quality Bar

Only write what's genuinely worth reading. Skip:
- Purely social chat
- Coordination messages
- Trivial exchanges

Write when there's:
- Substantive idea exploration
- Novel perspectives or connections
- Useful insights or analysis
- Meaningful uncertainty or debate
"""

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
