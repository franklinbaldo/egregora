# tests/unit/output_adapters/mkdocs/test_adapter_coverage.py

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, ANY
from datetime import datetime

from egregora.data_primitives.document import Document, DocumentType
from egregora.metadata.publishable import PublishableMetadata
from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter

class TestMkDocsAdapterCoverage:
    """Tests specifically designed to increase code coverage for MkDocsAdapter."""

    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = MkDocsAdapter()
        adapter.initialize(tmp_path)
        return adapter

    def test_write_media_skips_pii(self, adapter):
        """Test that media with pii_deleted=True is not written to disk."""
        doc = Document(
            content=b"secret data",
            type=DocumentType.MEDIA,
            metadata={
                "pii_deleted": True,
                "filename": "secret.jpg"
            }
        )

        # Determine expected path (media_dir / filename)
        expected_path = adapter.media_dir / "secret.jpg"

        # Ensure it doesn't exist
        assert not expected_path.exists()

        adapter.persist(doc)

        # Verify it still doesn't exist
        assert not expected_path.exists()

    def test_write_post_handles_invalid_date_string(self, adapter):
        """Test proper handling of unparseable date strings in post metadata."""
        doc = Document(
            content="content",
            type=DocumentType.POST,
            metadata={
                "title": "Bad Date Post",
                "slug": "bad-date",
                "date": "not-a-date-string",  # Invalid date
                "authors": ["uuid1"]
            }
        )

        with patch("egregora.output_adapters.mkdocs.adapter.yaml.dump") as mock_yaml:
            mock_yaml.return_value = "---\n"

            adapter.persist(doc)

            # Check what was passed to yaml dump
            args, _ = mock_yaml.call_args
            metadata = args[0]

            # Should remain as the original string since parsing failed
            assert metadata["date"] == "not-a-date-string"

    def test_write_profile_generates_fallback_avatar(self, adapter):
        """Test that missing avatar triggers generation of fallback URL."""
        doc = Document(
            content="Bio",
            type=DocumentType.PROFILE,
            metadata={
                "uuid": "user123",
                "name": "User Name"
                # No avatar provided
            }
        )

        with patch("egregora.output_adapters.mkdocs.adapter.generate_fallback_avatar_url") as mock_gen:
            mock_gen.return_value = "http://generated.avatar/1.jpg"

            # Mock yaml dump to capture metadata
            with patch("egregora.output_adapters.mkdocs.adapter.yaml.dump") as mock_yaml:
                mock_yaml.return_value = ""

                adapter.persist(doc)

                # Verify generator was called
                mock_gen.assert_called_with("user123")

                # Verify metadata has the generated avatar
                args, _ = mock_yaml.call_args
                metadata = args[0]
                assert metadata["avatar"] == "http://generated.avatar/1.jpg"
