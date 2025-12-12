"""MkDocs Output Sink for publishing feeds as Markdown files."""

from pathlib import Path

from egregora_v3.core.types import Document, DocumentStatus, Feed
from egregora_v3.core.utils import slugify


class MkDocsOutputSink:
    """Publishes a Feed as MkDocs-compatible Markdown files.

    Creates one .md file per published document, with YAML frontmatter.
    Also creates an index.md listing all posts.
    """

    def __init__(self, output_dir: Path) -> None:
        """Initialize the MkDocs output sink.

        Args:
            output_dir: Directory where markdown files will be written

        """
        self.output_dir = Path(output_dir)

    def publish(self, feed: Feed) -> None:
        """Publish the feed as MkDocs markdown files.

        Args:
            feed: The Feed to publish

        Only publishes documents with status=PUBLISHED.
        Creates parent directories if they don't exist.
        Cleans existing .md files before writing new ones.

        """
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Clean existing markdown files (but keep subdirectories)
        self._clean_markdown_files()

        # Filter published documents
        published_docs = [
            entry
            for entry in feed.entries
            if isinstance(entry, Document) and entry.status == DocumentStatus.PUBLISHED
        ]

        # Write individual markdown files
        for doc in published_docs:
            self._write_document(doc)

        # Create index page
        self._write_index(feed, published_docs)

    def _clean_markdown_files(self) -> None:
        """Remove existing .md files in output directory."""
        for md_file in self.output_dir.glob("*.md"):
            md_file.unlink()

    def _write_document(self, doc: Document) -> None:
        """Write a single document as a markdown file.

        Args:
            doc: Document to write

        """
        # Determine filename from slug or title
        filename = self._get_filename(doc)
        output_file = self.output_dir / f"{filename}.md"

        # Generate frontmatter
        frontmatter = self._generate_frontmatter(doc)

        # Combine frontmatter + content
        content = f"{frontmatter}\n{doc.content or ''}"

        # Write file
        output_file.write_text(content, encoding="utf-8")

    def _get_filename(self, doc: Document) -> str:
        """Get filename for a document.

        Uses slug if available, otherwise slugifies the title or ID.

        Args:
            doc: Document to get filename for

        Returns:
            Filename (without .md extension)

        """
        # Try slug from internal_metadata first
        if doc.slug:
            return doc.slug

        # Try slugifying the title
        if doc.title:
            slug = slugify(doc.title, max_len=60)
            if slug:
                return slug

        # Fallback to slugified ID
        return slugify(doc.id, max_len=60) or doc.id

    def _generate_frontmatter(self, doc: Document) -> str:
        """Generate YAML frontmatter for a document.

        Args:
            doc: Document to generate frontmatter for

        Returns:
            YAML frontmatter string with --- delimiters

        """
        lines = ["---"]

        # Title
        # Escape quotes in title
        title_escaped = doc.title.replace('"', '\\"')
        lines.append(f'title: "{title_escaped}"')

        # Date (use published if available, otherwise updated)
        date = doc.published or doc.updated
        lines.append(f"date: {date.strftime('%Y-%m-%d')}")

        # Authors
        if doc.authors:
            if len(doc.authors) == 1:
                lines.append(f"author: {doc.authors[0].name}")
            else:
                lines.append("authors:")
                lines.extend(f"  - {author.name}" for author in doc.authors)

        # Categories/tags
        if doc.categories:
            lines.append("tags:")
            lines.extend(f"  - {category.term}" for category in doc.categories)

        # Document type
        lines.append(f"type: {doc.doc_type.value}")

        # Status
        lines.append(f"status: {doc.status.value}")

        lines.append("---")

        return "\n".join(lines)

    def _write_index(self, feed: Feed, published_docs: list[Document]) -> None:
        """Write index.md listing all published posts.

        Args:
            feed: The Feed being published
            published_docs: List of published documents

        """
        index_file = self.output_dir / "index.md"

        lines = []

        # Title
        lines.append(f"# {feed.title}")
        lines.append("")

        # Feed metadata
        if feed.authors:
            author_names = ", ".join(author.name for author in feed.authors)
            lines.append(f"**Authors:** {author_names}")
            lines.append("")

        lines.append(f"**Last Updated:** {feed.updated.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Posts list
        lines.append("## Posts")
        lines.append("")

        if not published_docs:
            lines.append("*No posts yet.*")
        else:
            # Sort by date, newest first
            sorted_docs = sorted(
                published_docs,
                key=lambda d: d.published or d.updated,
                reverse=True,
            )

            for doc in sorted_docs:
                filename = self._get_filename(doc)
                date = doc.published or doc.updated
                date_str = date.strftime("%Y-%m-%d")

                # Markdown link
                lines.append(f"- [{doc.title}]({filename}.md) - {date_str}")

                # Add authors if available
                if doc.authors:
                    author_names = ", ".join(author.name for author in doc.authors)
                    lines.append(f"  *by {author_names}*")

                lines.append("")

        content = "\n".join(lines)
        index_file.write_text(content, encoding="utf-8")
