"""Tests for input/output abstraction layer."""

from pathlib import Path

import pytest

from egregora.core import input_registry, output_registry
from egregora.core.input_source import InputSource
from egregora.core.output_format import OutputFormat


class TestInputRegistry:
    """Test input source registry functionality."""

    def test_list_sources(self):
        """Test listing registered input sources."""
        sources = input_registry.list_sources()
        assert isinstance(sources, list)
        assert "whatsapp" in sources

    def test_get_whatsapp_source(self):
        """Test getting WhatsApp input source."""
        source = input_registry.get_source("whatsapp")
        assert isinstance(source, InputSource)
        assert source.source_type == "whatsapp"

    def test_get_invalid_source(self):
        """Test getting non-existent input source."""
        with pytest.raises(KeyError, match="not found"):
            input_registry.get_source("nonexistent")


class TestOutputRegistry:
    """Test output format registry functionality."""

    def test_list_formats(self):
        """Test listing registered output formats."""
        formats = output_registry.list_formats()
        assert isinstance(formats, list)
        assert "mkdocs" in formats

    def test_get_mkdocs_format(self):
        """Test getting MkDocs output format."""
        output = output_registry.get_format("mkdocs")
        assert isinstance(output, OutputFormat)
        assert output.format_type == "mkdocs"

    def test_get_invalid_format(self):
        """Test getting non-existent output format."""
        with pytest.raises(KeyError, match="not found"):
            output_registry.get_format("nonexistent")


class TestWhatsAppInputSource:
    """Test WhatsApp input source implementation."""

    def test_source_type(self):
        """Test WhatsApp source type identifier."""
        source = input_registry.get_source("whatsapp")
        assert source.source_type == "whatsapp"

    def test_supports_format_invalid(self):
        """Test format detection for invalid paths."""
        source = input_registry.get_source("whatsapp")

        # Non-existent path
        assert not source.supports_format(Path("/nonexistent.zip"))

        # Non-ZIP file
        assert not source.supports_format(Path(__file__))

    def test_detect_whatsapp_zip(self, tmp_path):
        """Test auto-detection of WhatsApp ZIP."""
        # Create a mock WhatsApp ZIP
        import zipfile

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("_chat.txt", "Test content")

        source = input_registry.get_source("whatsapp")
        assert source.supports_format(zip_path)

        # Test auto-detection
        detected = input_registry.detect_source(zip_path)
        assert detected is not None
        assert detected.source_type == "whatsapp"


class TestMkDocsOutputFormat:
    """Test MkDocs output format implementation."""

    def test_format_type(self):
        """Test MkDocs format type identifier."""
        output = output_registry.get_format("mkdocs")
        assert output.format_type == "mkdocs"

    def test_supports_site_invalid(self):
        """Test site detection for invalid paths."""
        output = output_registry.get_format("mkdocs")

        # Non-existent path
        assert not output.supports_site(Path("/nonexistent"))

    def test_detect_mkdocs_site(self, tmp_path):
        """Test auto-detection of MkDocs site."""
        # Create mock mkdocs.yml
        mkdocs_yml = tmp_path / "mkdocs.yml"
        mkdocs_yml.write_text("site_name: Test\n")

        output = output_registry.get_format("mkdocs")
        assert output.supports_site(tmp_path)

        # Test auto-detection
        detected = output_registry.detect_format(tmp_path)
        assert detected is not None
        assert detected.format_type == "mkdocs"

    def test_scaffold_site(self, tmp_path):
        """Test MkDocs site scaffolding."""
        output = output_registry.get_format("mkdocs")
        site_root = tmp_path / "test-site"

        config_path, created = output.scaffold_site(site_root, "Test Site")

        assert created
        assert config_path.exists()
        assert config_path.name == "mkdocs.yml"

        # Check directory structure
        assert (site_root / "docs").exists()
        assert (site_root / "docs" / "posts").exists()
        assert (site_root / "docs" / "profiles").exists()
        assert (site_root / "docs" / "media").exists()

    def test_resolve_paths(self, tmp_path):
        """Test path resolution for MkDocs site."""
        output = output_registry.get_format("mkdocs")
        site_root = tmp_path / "test-site"

        # Scaffold first
        output.scaffold_site(site_root, "Test Site")

        # Resolve paths
        config = output.resolve_paths(site_root)

        assert config.site_root == site_root
        assert config.docs_dir == site_root / "docs"
        assert config.posts_dir.exists()
        assert config.profiles_dir.exists()
        assert config.media_dir.exists()

    def test_write_post(self, tmp_path):
        """Test writing a blog post."""
        output = output_registry.get_format("mkdocs")
        output_dir = tmp_path / "posts"
        output_dir.mkdir()

        metadata = {
            "title": "Test Post",
            "slug": "test-post",
            "date": "2025-01-15",
            "tags": ["test", "example"],
            "summary": "A test post",
        }

        post_path = output.write_post(
            content="# Test Post\n\nThis is a test.",
            metadata=metadata,
            output_dir=output_dir,
        )

        assert Path(post_path).exists()
        assert "2025-01-15" in post_path
        assert "test-post" in post_path

        # Check content
        content = Path(post_path).read_text()
        assert "---" in content  # YAML front matter
        assert "title: Test Post" in content
        assert "# Test Post" in content

    def test_write_profile(self, tmp_path):
        """Test writing an author profile."""
        output = output_registry.get_format("mkdocs")
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        profile_data = {
            "content": "# John Doe\n\nSoftware engineer and writer.",
        }

        profile_path = output.write_profile(
            author_id="abc123",
            profile_data=profile_data,
            profiles_dir=profiles_dir,
        )

        assert Path(profile_path).exists()
        assert "abc123.md" in profile_path

        # Check content
        content = Path(profile_path).read_text()
        assert "John Doe" in content

    def test_get_markdown_extensions(self):
        """Test getting supported markdown extensions."""
        output = output_registry.get_format("mkdocs")
        extensions = output.get_markdown_extensions()

        assert isinstance(extensions, list)
        assert len(extensions) > 0
        assert "tables" in extensions
        assert "fenced_code" in extensions


class TestIntegration:
    """Integration tests for the abstraction layer."""

    def test_auto_detection(self, tmp_path):
        """Test automatic detection of input sources and output formats."""
        # Create WhatsApp ZIP
        import zipfile

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("_chat.txt", "Test")

        # Create MkDocs site
        site_root = tmp_path / "site"
        (site_root / "mkdocs.yml").mkdir(parents=True, exist_ok=True)
        (site_root / "mkdocs.yml").write_text("site_name: Test\n")

        # Auto-detect
        source = input_registry.detect_source(zip_path)
        output = output_registry.detect_format(site_root)

        assert source is not None
        assert source.source_type == "whatsapp"
        assert output is not None
        assert output.format_type == "mkdocs"
