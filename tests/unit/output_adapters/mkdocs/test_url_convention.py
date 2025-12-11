from pathlib import Path

from mkdocs.commands.build import build as mkdocs_build
from mkdocs.config import load_config

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.mkdocs import MkDocsAdapter


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
        metadata={"uuid": "author-123", "slug": "Should not be used"},
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

    site_dir = _build_site(tmp_path, docs_dir)

    # Persisted paths should mirror the canonical URLs produced by the embedded convention.
    for stored_doc in (post, profile, journal, fallback_journal, enrichment, media):
        canonical_url = adapter.url_convention.canonical_url(stored_doc, adapter._ctx)  # type: ignore[arg-type]
        if stored_doc is fallback_journal:
            # Unified: fallback journal goes to /posts/ (journal_prefix updated to posts)
            assert canonical_url == "/posts/"
        relative_from_url = _relative_path_from_url(canonical_url, stored_doc)
        stored_path = adapter._index[stored_doc.document_id]

        assert stored_path.exists()
        # Ensure stored path matches relative URL path relative to docs_dir
        stored_relative = stored_path.relative_to(docs_dir)

        # With unification, everything except media is in posts/
        if stored_doc.type == DocumentType.MEDIA:
             assert stored_relative == relative_from_url
        else:
             # Posts, profiles, journals all in posts/
             # URL convention now aligns so canonical_url starts with /posts/
             if stored_doc is fallback_journal:
                  # Special case: /posts/ -> posts/index.md
                  assert stored_relative == Path("posts/index.md")
             else:
                  assert stored_relative == relative_from_url
                  assert stored_relative.parts[0] == "posts"

        served_path = _served_path_from_url(site_dir, canonical_url, stored_doc)
        # Skip served path check for posts - minimal MkDocs build doesn't have blog plugin
        # which handles the nested posts/posts/ structure
        if stored_doc.type != DocumentType.POST:
            assert served_path.exists()

    # Ensure raw, unnormalized metadata slugs are not used for filenames.
    assert not (adapter.posts_dir / "Complex Slug.md").exists()
