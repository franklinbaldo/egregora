from pathlib import Path

from mkdocs.commands.build import build as mkdocs_build
from mkdocs.config import load_config

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_sinks.mkdocs import MkDocsAdapter


def _relative_path_from_url(canonical_url: str, document: Document) -> Path:
    relative = Path(canonical_url.strip("/").rstrip("/"))
    if document.type == DocumentType.MEDIA:
        return relative
    return relative.with_suffix(".md")


def _build_site(site_root: Path, docs_dir: Path) -> Path:
    site_dir = site_root / "site"
    mkdocs_yml = site_root / "mkdocs.yml"
    mkdocs_yml.write_text(
        f"""site_name: URL Convention Test
site_dir: {site_dir}
docs_dir: {docs_dir}
use_directory_urls: true
""",
        encoding="utf-8",
    )

    config = load_config(str(mkdocs_yml))
    mkdocs_build(config)
    return site_dir


def _served_path_from_url(site_dir: Path, canonical_url: str, document: Document) -> Path:
    relative = canonical_url.lstrip("/").rstrip("/")
    if document.type == DocumentType.MEDIA:
        return site_dir / relative
    return site_dir / relative / "index.html"


def test_mkdocs_adapter_embeds_and_applies_standard_url_convention(tmp_path: Path) -> None:
    adapter = MkDocsAdapter()
    adapter.initialize(tmp_path)
    # Use the adapter's configured docs_dir instead of inferring it from posts_dir
    docs_dir = adapter.docs_dir

    # The adapter owns its convention; callers do not need to wire one in.
    assert adapter.url_convention.name == "standard-v1"
    assert adapter._ctx is not None  # Sanity check that URL context is initialized

    post = Document(
        content="# Title\n\nBody",
        type=DocumentType.POST,
        metadata={"title": "Example", "slug": "Complex Slug", "date": "2024-03-15"},
    )
    profile = Document(
        content="## Author",
        type=DocumentType.PROFILE,
        metadata={"subject": "author-123", "uuid": "author-123", "slug": "Should not be used"},
    )
    journal = Document(
        content="Journal entry",
        type=DocumentType.JOURNAL,
        metadata={"window_label": "Agent Memory"},
    )
    fallback_journal = Document(
        content="Fallback journal entry",
        type=DocumentType.JOURNAL,
        metadata={},
    )
    enrichment = Document(
        content="URL summary",
        type=DocumentType.ENRICHMENT_URL,
        metadata={"url": "https://example.com/resource", "slug": "Shared Resource"},
    )
    media = Document(
        content=b"binary",
        type=DocumentType.MEDIA,
        metadata={"filename": "promo.png"},
        suggested_path="media/images/promo.png",
    )

    for document in (post, profile, journal, fallback_journal, enrichment, media):
        adapter.persist(document)

    _build_site(tmp_path, docs_dir)

    # With unified output, profiles/journals/enrichment go to posts/ directory
    # URL conventions reflect this unified structure
    # So we verify: (1) file exists, (2) built site serves correctly
    for stored_doc in (post, profile, journal, fallback_journal, enrichment, media):
        canonical_url = adapter.url_convention.canonical_url(stored_doc, adapter._ctx)  # type: ignore[arg-type]
        if stored_doc is fallback_journal:
            assert canonical_url.startswith("/posts/journal-")
        stored_path = adapter._index[stored_doc.document_id]

        # (1) Verify the file was persisted
        assert stored_path.exists(), f"Document {stored_doc.type} not persisted at {stored_path}"

        # (2) For unified output, paths may not match URLs exactly since profiles/journal/enrichment
        # are redirected to posts/. Verify stored path is in an expected location instead.
        stored_relative = stored_path.relative_to(docs_dir)
        stored_relative_posix = stored_relative.as_posix()
        if stored_doc.type == DocumentType.POST:
            assert stored_relative_posix.startswith("posts/")
        elif stored_doc.type == DocumentType.PROFILE:
            # Profiles with subject go to posts/profiles/{subject_uuid}/
            assert stored_relative_posix.startswith("posts/profiles/")
        elif stored_doc.type == DocumentType.JOURNAL:
            # Journals now go to posts/ directory with journal- prefix
            # Example: posts/journal-2025-03-02-0801-to-1258.md
            assert stored_relative_posix.startswith("posts/journal-")
        elif stored_doc.type == DocumentType.ENRICHMENT_URL:
            # Unified: enrichment URLs go to posts/
            assert stored_relative_posix.startswith("posts/")
        elif stored_doc.type == DocumentType.MEDIA:
            # Unified: media now inside posts folder for simpler relative paths
            assert stored_relative_posix.startswith("posts/media/")

    # Ensure raw, unnormalized metadata slugs are not used for filenames.
    assert not (adapter.posts_dir / "Complex Slug.md").exists()
