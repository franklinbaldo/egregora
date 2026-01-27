"""Behavioral tests for MkDocsAdapter."""

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.exceptions import AdapterNotInitializedError
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def site_root(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    # Create required dirs structure roughly (MkDocsPaths expects config or default)
    # Default is site_root/docs
    (root / "docs").mkdir()
    return root


@pytest.fixture
def adapter(site_root):
    adapter = MkDocsAdapter()
    adapter.initialize(site_root)
    return adapter


def test_initialize_sets_up_directories(site_root):
    """Verify initialization creates necessary directories."""
    # Given
    adapter = MkDocsAdapter()

    # When
    adapter.initialize(site_root)

    # Then
    assert (site_root / "docs" / "posts").exists()
    # Default paths per config/settings.py
    assert (site_root / "docs" / "posts" / "media").exists()
    assert (site_root / "docs" / "posts" / "profiles").exists()
    assert adapter._initialized


def test_persist_post(adapter, site_root):
    """Verify persisting a POST document."""
    # Given
    doc = Document(
        content="Post content",
        type=DocumentType.POST,
        metadata={"slug": "test-post", "date": "2023-01-01", "title": "Test Post"},
    )

    # When
    adapter.persist(doc)

    # Then
    # MkDocs posts have date prefix: YYYY-MM-DD-slug.md
    post_path = site_root / "docs" / "posts" / "2023-01-01-test-post.md"
    assert post_path.exists()
    content = post_path.read_text()
    assert "Post content" in content
    assert "title: Test Post" in content


def test_persist_profile(adapter, site_root):
    """Verify persisting a PROFILE document routes to author directory."""
    # Given
    author_uuid = "1234-5678"
    doc = Document(
        content="Profile content",
        type=DocumentType.PROFILE,
        metadata={"slug": "my-profile", "subject": author_uuid, "uuid": author_uuid},
    )

    # When
    adapter.persist(doc)

    # Then
    # Default profiles_dir is docs/posts/profiles
    profile_path = site_root / "docs" / "posts" / "profiles" / author_uuid / "my-profile.md"
    assert profile_path.exists()
    content = profile_path.read_text()
    assert "Profile content" in content
    # Verify frontmatter has type: profile
    assert "type: profile" in content


def test_persist_journal(adapter, site_root):
    """Verify persisting a JOURNAL document."""
    # Given
    doc = Document(content="Journal content", type=DocumentType.JOURNAL, metadata={"slug": "entry-1"})

    # When
    adapter.persist(doc)

    # Then
    # Based on adapter logic, it goes to posts_dir with journal- prefix
    journal_path = site_root / "docs" / "posts" / "journal-entry-1.md"
    assert journal_path.exists()
    content = journal_path.read_text()
    assert "type: journal" in content
    assert "Journal content" in content


<<<<<<< HEAD
def test_list(adapter, site_root):
=======
def test_list_documents(adapter, site_root):
>>>>>>> origin/pr/2658
    """Verify listing documents from filesystem."""
    # Given
    p1 = site_root / "docs" / "posts" / "p1.md"
    p1.write_text("---\ntitle: P1\n---\nC1", encoding="utf-8")

    # When
    docs = list(adapter.list())

    # Then
    identifiers = [d.identifier for d in docs]
    # Check if we find the file. Identifier format depends on implementation.
    # Adapter uses: str(path.relative_to(self._site_root))
    assert "docs/posts/p1.md" in identifiers


def test_load_config(adapter, site_root):
    """Verify loading mkdocs config."""
    # Given
    # MkDocsPaths looks in .egregora/mkdocs.yml by default
    config_dir = site_root / ".egregora"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "mkdocs.yml").write_text("site_name: Test Site", encoding="utf-8")

    # When
    config = adapter.load_config(site_root)

    # Then
    assert config["site_name"] == "Test Site"


def test_get_markdown_extensions_default(adapter):
    """Verify default markdown extensions."""
    # When
    exts = adapter.get_markdown_extensions()

    # Then
    assert "admonition" in exts
    assert "pymdownx.superfences" in exts


def test_resolve_document_path(adapter, site_root):
    """Verify resolving document path."""
    # Given
    rel_path = "posts/test.md"

    # When
    abs_path = adapter.resolve_document_path(rel_path)

    # Then
    assert abs_path == site_root / rel_path


def test_resolve_document_path_uninitialized():
    """Verify error when not initialized."""
    # Given
    adapter = MkDocsAdapter()

    # When/Then
    with pytest.raises(AdapterNotInitializedError):
        adapter.resolve_document_path("foo")


def test_scaffold_site(adapter, site_root):
    """Verify site scaffolding."""
    # Given
    # adapter is already initialized with site_root

    # When
    adapter.scaffold_site(site_root, "My Site")

    # Then
    # Scaffolder creates mkdocs.yml in .egregora usually, or root?
    # MkDocsPaths defaults to .egregora/mkdocs.yml
    assert (site_root / ".egregora" / "mkdocs.yml").exists()
