import pytest
from pathlib import Path
from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter
from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.data_primitives.text import slugify

def test_profile_path_traversal(tmp_path):
    """Test that malicious author_uuid cannot write outside profiles directory.

    This test attempts to use directory traversal characters in the author UUID.
    It asserts that the file is NOT written to the traversed location, preventing
    arbitrary file write vulnerabilities.
    """
    site_root = tmp_path / "site"
    site_root.mkdir()
    (site_root / "mkdocs.yml").touch()

    adapter = MkDocsAdapter()
    adapter.initialize(site_root)

    # malicious_uuid tries to traverse up 3 levels: profiles -> posts -> docs -> site_root
    malicious_uuid = "../../../evil_root"

    doc = Document(
        content="Safe Content",
        type=DocumentType.PROFILE,
        metadata={
            "uuid": malicious_uuid,
            "subject": malicious_uuid,
            "slug": "exploit"
        }
    )

    adapter.persist(doc)

    # The file should NOT exist at the traversed path
    escaped_path = site_root / "evil_root" / "exploit.md"
    assert not escaped_path.exists(), f"Path traversal succeeded! File written to {escaped_path}"

    # Instead, it should be safely slugified inside the profiles directory
    # slugify("../../../evil_root") -> "evil-root" (depending on slugify implementation)
    # We check if it exists within profiles_dir

    safe_uuid_slug = slugify(malicious_uuid)
    expected_safe_path = adapter.profiles_dir / safe_uuid_slug / "exploit.md"

    assert expected_safe_path.exists(), f"File should have been written to safe path {expected_safe_path}"
