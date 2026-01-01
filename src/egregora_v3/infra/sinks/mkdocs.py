"""MkDocs Output Sink for publishing feeds as Markdown files."""

from pathlib import Path
import yaml
from egregora_v3.core.types import Document, DocumentStatus, Feed
from egregora.utils.text import slugify


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
        self._jinja_env = self._setup_jinja_env()

    def _setup_jinja_env(self) -> "jinja2.Environment":
        """Configure Jinja2 environment for rendering templates."""
        from jinja2 import Environment, PackageLoader

        return Environment(
            loader=PackageLoader("egregora_v3.infra.sinks", "templates"),
            autoescape=False,  # We are generating Markdown, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

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
        published_docs = feed.get_published_documents()

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
        content = f"---\n{frontmatter}---\n\n{doc.content or ''}"

        # Write file
        output_file.write_text(content, encoding="utf-8")

    def _get_filename(self, doc: Document) -> str:
        """Get filename for a document using a declarative strategy chain.

        Tries strategies in order:
        1. Use the document's explicit slug.
        2. Slugify the document's title (if title exists).
        3. Slugify the document's ID as a fallback.

        Args:
            doc: Document to get filename for

        Returns:
            Filename (without .md extension)

        """
        # A list of potential filename values. The first valid one is used.
        potential_filenames = [
            doc.slug,
            slugify(doc.title, max_len=60) if doc.title else None,
            slugify(doc.id, max_len=60),
        ]

        for filename in potential_filenames:
            if filename:
                return filename

        # Final fallback to the raw ID if all slugification fails
        return doc.id

    def _generate_frontmatter(self, doc: Document) -> str:
        """Generate YAML frontmatter for a document declaratively.

        Args:
            doc: Document to generate frontmatter for

        Returns:
            YAML frontmatter string with --- delimiters

        """
        frontmatter_data = {
            "title": doc.title,
            "date": (doc.published or doc.updated).strftime("%Y-%m-%d"),
        }

        # Handle authors: 'author' for single, 'authors' for multiple.
        if doc.authors:
            if len(doc.authors) == 1:
                frontmatter_data["author"] = doc.authors[0].name
            else:
                frontmatter_data["authors"] = [author.name for author in doc.authors]

        # Handle categories/tags
        if doc.categories:
            frontmatter_data["tags"] = [c.term for c in doc.categories]

        frontmatter_data["type"] = doc.doc_type.value
        frontmatter_data["status"] = doc.status.value

        # Serialize to YAML
        return yaml.dump(frontmatter_data, sort_keys=False, default_flow_style=False)

    def _write_index(self, feed: Feed, published_docs: list[Document]) -> None:
        """Write index.md listing all published posts using a Jinja2 template.

        Args:
            feed: The Feed being published
            published_docs: List of published documents

        """
        index_file = self.output_dir / "index.md"

        # Enhance documents with their target filenames for the template
        docs_with_filenames = []
        for doc in published_docs:
            filename = self._get_filename(doc)
            docs_with_filenames.append({"doc": doc, "filename": filename})

        # Sort documents by date, newest first, for the template
        sorted_docs = sorted(
            docs_with_filenames,
            key=lambda d: d["doc"].published or d["doc"].updated,
            reverse=True,
        )

        template = self._jinja_env.get_template("index.md.jinja")
        content = template.render(feed=feed, sorted_docs_data=sorted_docs)

        index_file.write_text(content, encoding="utf-8")
