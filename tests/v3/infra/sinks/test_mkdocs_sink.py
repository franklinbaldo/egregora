"""Tests for the MkDocsOutputSink."""

from datetime import datetime, timezone
from pathlib import Path
import yaml
import pytest
from egregora_v3.core.types import (
    Author,
    Category,
    Document,
    DocumentStatus,
    DocumentType,
)
from egregora_v3.infra.sinks.mkdocs import MkDocsOutputSink


@pytest.fixture
def mkdocs_sink(tmp_path: Path) -> MkDocsOutputSink:
    """Fixture for MkDocsOutputSink."""
    return MkDocsOutputSink(output_dir=tmp_path)


def test_generate_frontmatter_single_author(mkdocs_sink: MkDocsOutputSink):
    """Test frontmatter generation for a document with a single author."""
    doc = Document(
        id="test-doc-1",
        title='Test Document "with quotes"',
        updated=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        published=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        authors=[Author(name="John Doe")],
        categories=[Category(term="test"), Category(term="sample")],
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        content="This is the content.",
    )

    frontmatter_str = mkdocs_sink._generate_frontmatter(doc)

    # The new implementation will use a standard YAML serializer,
    # so we'll test against that expected output.
    # The current implementation will fail this test.
    expected_data = {
        'title': 'Test Document "with quotes"',
        'date': '2023-01-01',
        'author': 'John Doe',
        'tags': ['test', 'sample'],
        'type': 'post',
        'status': 'published'
    }

    expected_yaml = "---\n" + yaml.dump(expected_data, sort_keys=False) + "---\n"

    # Strip the final newline from the generated frontmatter for comparison
    assert frontmatter_str.strip() == expected_yaml.strip()


def test_generate_frontmatter_multiple_authors(mkdocs_sink: MkDocsOutputSink):
    """Test frontmatter generation for a document with multiple authors."""
    doc = Document(
        id="test-doc-2",
        title="Another Test Document",
        updated=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        published=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        authors=[Author(name="John Doe"), Author(name="Jane Doe")],
        categories=[],
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        content="This is the content.",
    )

    frontmatter_str = mkdocs_sink._generate_frontmatter(doc)

    expected_data = {
        'title': 'Another Test Document',
        'date': '2023-01-02',
        'authors': ['John Doe', 'Jane Doe'],
        'type': 'post',
        'status': 'published'
    }

    expected_yaml = "---\n" + yaml.dump(expected_data, sort_keys=False) + "---\n"

    assert frontmatter_str.strip() == expected_yaml.strip()
