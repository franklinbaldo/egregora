"""Tool definitions for writer module - LLM function calling."""

from collections.abc import Sequence
from functools import lru_cache

from google.genai import types as genai_types
from pydantic import BaseModel


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
def _writer_tools() -> Sequence[genai_types.Tool]:
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
                ),
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

    search_media_decl = genai_types.FunctionDeclaration(
        name="search_media",
        description=(
            "Search for relevant media (images, memes, videos, audio) by description or topic. "
            "Returns media that was previously shared in the group conversations. "
            "Use this to find visual content to illustrate your blog posts."
        ),
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "query": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description=(
                        "Natural language search query describing the media you're looking for. "
                        "Examples: 'funny meme about procrastination', 'chart about productivity', "
                        "'image related to AI safety'"
                    ),
                ),
                "media_types": genai_types.Schema(
                    type=genai_types.Type.ARRAY,
                    description=(
                        "Optional filter by media type. Valid types: 'image', 'video', 'audio', 'document'. "
                        "If not specified, searches all media types."
                    ),
                    items=genai_types.Schema(type=genai_types.Type.STRING),
                    nullable=True,
                ),
                "limit": genai_types.Schema(
                    type=genai_types.Type.INTEGER,
                    description="Maximum number of results to return (default: 5)",
                    nullable=True,
                ),
            },
            required=["query"],
        ),
    )

    annotate_conversation_decl = genai_types.FunctionDeclaration(
        name="annotate_conversation",
        description=(
            "Store a private annotation linked to a conversation message or another annotation, "
            "so it can be surfaced automatically during future writing sessions."
        ),
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "parent_id": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Identifier of the parent object (message or annotation)",
                ),
                "parent_type": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Type of the parent object ('message' or 'annotation')",
                ),
                "commentary": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Commentary to remember for the specified parent object",
                ),
            },
            required=["parent_id", "parent_type", "commentary"],
        ),
    )

    generate_banner_decl = genai_types.FunctionDeclaration(
        name="generate_banner",
        description=(
            "Generate a cover/banner image for a blog post using AI. "
            "Creates a striking, concept-driven visual that captures the essence of the article. "
            "Use this AFTER writing a post to create its banner image."
        ),
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "post_slug": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="The slug of the post to generate a banner for",
                ),
                "title": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="The post title to base the banner design on",
                ),
                "summary": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Brief summary or key themes to inform the banner design",
                ),
            },
            required=["post_slug", "title", "summary"],
        ),
    )

    return [
        genai_types.Tool(
            function_declarations=[
                write_post_decl,
                read_profile_decl,
                write_profile_decl,
                search_media_decl,
                annotate_conversation_decl,
                generate_banner_decl,
            ],
        ),
    ]
