"""write_post tool: Save blog posts with front matter (CMS-like interface for LLM)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from .privacy import validate_newsletter_privacy


@dataclass(frozen=True, slots=True)
class PostMetadata:
    """Structured representation of metadata required to publish a post."""

    title: str
    slug: str
    date: str
    tags: list[str] | None = None
    summary: str | None = None
    authors: list[str] | None = None
    category: str | None = None

    @classmethod
    def from_mapping(cls, metadata: Mapping[str, object]) -> "PostMetadata":
        """Validate and coerce metadata provided by the LLM."""

        missing = [key for key in ("title", "slug", "date") if key not in metadata]
        if missing:
            raise ValueError(f"Missing required metadata: {', '.join(missing)}")

        title = cls._coerce_str(metadata["title"], "title")
        slug = cls._coerce_str(metadata["slug"], "slug")
        date = cls._coerce_str(metadata["date"], "date")

        tags = cls._coerce_str_list(metadata.get("tags"), "tags")
        summary = cls._coerce_optional_str(metadata.get("summary"), "summary")
        authors = cls._coerce_str_list(metadata.get("authors"), "authors")
        category = cls._coerce_optional_str(metadata.get("category"), "category")

        return cls(
            title=title,
            slug=slug,
            date=date,
            tags=tags,
            summary=summary,
            authors=authors,
            category=category,
        )

    def to_front_matter(self) -> dict[str, str | list[str] | None]:
        """Create the YAML front matter structure for the post."""

        return {
            "title": self.title,
            "date": self.date,
            "slug": self.slug,
            "tags": self.tags,
            "summary": self.summary,
            "authors": self.authors,
            "category": self.category,
        }

    @staticmethod
    def _coerce_str(value: object, field_name: str) -> str:
        if isinstance(value, str):
            return value
        raise ValueError(f"Expected '{field_name}' to be a string, got {type(value).__name__}")

    @staticmethod
    def _coerce_optional_str(value: object | None, field_name: str) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError(f"Expected '{field_name}' to be a string if provided, got {type(value).__name__}")

    @staticmethod
    def _coerce_str_list(value: object | None, field_name: str) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            str_values = []
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(
                        f"Expected every item in '{field_name}' to be a string, got {type(item).__name__}"
                    )
                str_values.append(item)
            return list(str_values)
        raise ValueError(
            f"Expected '{field_name}' to be a sequence of strings if provided, got {type(value).__name__}"
        )


def write_post(
    content: str,
    metadata: PostMetadata | Mapping[str, object],
    output_dir: Path = Path("output/posts"),
) -> str:
    """
    Save a blog post with YAML front matter.

    This is a tool for the LLM to use as a CMS. The LLM decides:
    - How many posts to create (0-N per period)
    - Title, slug, tags, summary, authors
    - Post content

    Args:
        content: Markdown post content
        metadata: {
            "title": "Post Title",
            "slug": "post-slug",
            "date": "2025-01-01",
            "tags": ["AI", "ethics"],
            "summary": "Brief summary",
            "authors": ["a1b2c3d4"],  # anonymized IDs
            "category": "Optional category"
        }

    Returns:
        Path where post was saved

    Raises:
        PrivacyViolationError: If content contains PII (phone numbers, etc)
        ValueError: If required metadata is missing
    """

    validate_newsletter_privacy(content)

    parsed_metadata = metadata if isinstance(metadata, PostMetadata) else PostMetadata.from_mapping(metadata)

    front_matter = parsed_metadata.to_front_matter()

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)

    full_post = f"---\n{yaml_front}---\n\n{content}"

    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{parsed_metadata.date}-{parsed_metadata.slug}.md"
    filepath = output_dir / filename

    filepath.write_text(full_post, encoding="utf-8")

    return str(filepath)
