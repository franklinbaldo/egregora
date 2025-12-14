"""Test media path resolution to debug duplication issue."""

from pathlib import Path
from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.conventions import StandardUrlConvention, RouteConfig
from egregora.data_primitives.protocols import UrlContext


def test_media_url_generation():
    """Test that media URLs are generated correctly."""
    # Create a media document like the enricher does
    media_doc = Document(
        content=b"fake image bytes",
        type=DocumentType.MEDIA,
        metadata={
            "filename": "test-image.jpg",
            "media_type": "image/jpeg",
            "slug": "test-image",
        },
    )
   
    # Create URL convention
    convention = StandardUrlConvention()
    
    # Create context (empty site_prefix)
    ctx = UrlContext(base_url="", site_prefix="")
    
    # Generate URL
    url = convention.canonical_url(media_doc, ctx)
    
    print(f"Generated URL: {url}")
    print(f"Expected: /media/test-image.jpg")
    
    assert url == "/media/test-image.jpg", f"Got {url}"


def test_media_dir_calculation():
    """Test how media_dir is calculated."""
    from egregora.output_adapters.mkdocs.paths import derive_mkdocs_paths
    
    # Create a fake site root
    site_root = Path("/tmp/test-site")
    
    # Get paths (this will load default config)
    try:
        paths = derive_mkdocs_paths(site_root)
        print(f"media_dir: {paths['media_dir']}")
        print(f"posts_dir: {paths['posts_dir']}")
        print(f"docs_dir: {paths['docs_dir']}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 1: Media URL Generation")
    print("=" * 60)
    test_media_url_generation()
    
    print("\n" + "=" * 60)
    print("TEST 2: Media Dir Calculation")
    print("=" * 60)
    test_media_dir_calculation()
    
    print("\n✅ All tests passed!")
