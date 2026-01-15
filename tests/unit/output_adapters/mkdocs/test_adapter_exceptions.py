"""Tests for structured exception handling in the MkDocsAdapter."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.exceptions import (
    AdapterNotInitializedError,
    ConfigLoadError,
    DocumentNotFoundError,
    DocumentParsingError,
    UnsupportedDocumentTypeError,
)
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def adapter(tmp_path: Path) -> MkDocsAdapter:
    """Provides an initialized MkDocsAdapter instance."""
    adapter = MkDocsAdapter()
    (tmp_path / ".egregora").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "posts").mkdir()
    (tmp_path / ".egregora" / "mkdocs.yml").write_text("site_name: Test Site")
    adapter.initialize(tmp_path)
    return adapter


def test_get_raises_document_not_found_error(adapter: MkDocsAdapter):
    """Verify get() raises DocumentNotFoundError for a non-existent document."""
    with pytest.raises(DocumentNotFoundError) as excinfo:
        adapter.get(DocumentType.POST, "non-existent-slug")
    assert excinfo.value.doc_type == DocumentType.POST.value
    assert excinfo.value.identifier == "non-existent-slug"




def test_load_config_raises_config_load_error_on_bad_yaml(tmp_path: Path):
    """Verify load_config() raises ConfigLoadError on YAMLError."""
    adapter = MkDocsAdapter()
    (tmp_path / ".egregora").mkdir()
    bad_config = tmp_path / ".egregora" / "mkdocs.yml"
    bad_config.write_text("site_name: Test\ninvalid_yaml: [one, two:")

    with pytest.raises(ConfigLoadError) as excinfo:
        adapter.load_config(tmp_path)
    assert str(bad_config) in excinfo.value.path
    assert "parsing a flow node" in excinfo.value.reason


def test_resolve_document_path_raises_adapter_not_initialized_error():
    """Verify a public method raises AdapterNotInitializedError if not initialized."""
    adapter = MkDocsAdapter()  # Not initialized
    with pytest.raises(AdapterNotInitializedError):
        adapter.resolve_document_path("some/path.md")


def test_persist_adds_related_posts_to_frontmatter(adapter: MkDocsAdapter):
    """Verify that `persist` adds `related_posts` to frontmatter based on shared tags."""
    # Create some existing posts
    post1_meta = {"title": "Post 1", "slug": "post-1", "date": "2025-01-01", "tags": ["python", "testing"]}
    post2_meta = {
        "title": "Post 2",
        "slug": "post-2",
        "date": "2025-01-02",
        "tags": ["python", "refactoring"],
    }
    post3_meta = {"title": "Post 3", "slug": "post-3", "date": "2025-01-03", "tags": ["testing", "devops"]}

    doc1 = Document(content="Content 1", type=DocumentType.POST, metadata=post1_meta)
    doc2 = Document(content="Content 2", type=DocumentType.POST, metadata=post2_meta)
    doc3 = Document(content="Content 3", type=DocumentType.POST, metadata=post3_meta)

    # Create a new post that shares tags with the existing posts
    new_post_meta = {
        "title": "New Post",
        "slug": "new-post",
        "date": "2025-01-04",
        "tags": ["python", "devops"],
    }
    new_post_content = "This is a new post."
    new_post_doc = Document(content=new_post_content, type=DocumentType.POST, metadata=new_post_meta)

    # Since `documents()` now reads from the DB, we mock its return value
    # to simulate the presence of other posts.
    with patch.object(adapter, "documents", return_value=[doc1, doc2, doc3]):
        with patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries"):
            adapter.persist(new_post_doc)

    # Verify that the new post's frontmatter contains the related posts
    new_post_path = adapter.posts_dir / "2025-01-04-new-post.md"
    assert new_post_path.exists()

    with new_post_path.open(encoding="utf-8") as f:
        _, frontmatter_str, _ = f.read().split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_str)

    assert "related_posts" in frontmatter
    related_posts = frontmatter["related_posts"]
    assert len(related_posts) == 3

    related_titles = {post["title"] for post in related_posts}
    assert related_titles == {"Post 1", "Post 2", "Post 3"}


def test_persist_handles_filename_collisions(adapter: MkDocsAdapter):
    """Verify that `persist` handles filename collisions by appending a numeric suffix."""
    post1_meta = {"title": "Collision Post", "slug": "collision-post", "date": "2025-01-16"}
    post2_meta = {"title": "Collision Post", "slug": "collision-post", "date": "2025-01-16"}

    with patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries"):
        adapter.persist(Document(content="Content 1", type=DocumentType.POST, metadata=post1_meta))
        adapter.persist(Document(content="Content 2", type=DocumentType.POST, metadata=post2_meta))

    first_path = adapter.posts_dir / "2025-01-16-collision-post.md"
    second_path = adapter.posts_dir / "2025-01-16-collision-post-2.md"

    assert first_path.exists()
    assert second_path.exists()
