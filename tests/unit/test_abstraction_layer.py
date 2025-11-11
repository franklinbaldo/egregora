"""Tests for input/output abstraction layer."""

import zipfile
from pathlib import Path

import pytest

from egregora.ingestion import input_registry  # Import from ingestion to trigger registration
from egregora.rendering.base import OutputFormat, output_registry
from egregora.sources.base import InputSource


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
        # Create mock mkdocs.yml in .egregora/ (MODERN location)
        egregora_dir = tmp_path / ".egregora"
        egregora_dir.mkdir()
        mkdocs_yml = egregora_dir / "mkdocs.yml"
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

        # Check directory structure (MODERN: content at root level, not in docs/)
        assert (site_root / "posts").exists()
        assert (site_root / "profiles").exists()
        assert (site_root / "media").exists()
        assert (site_root / ".egregora").exists()
        assert (site_root / ".egregora" / "mkdocs.yml").exists()

    def test_scaffold_refuses_if_egregora_mkdocs_exists(self, tmp_path):
        """Test that scaffold refuses to init if .egregora/mkdocs.yml exists."""
        output = output_registry.get_format("mkdocs")
        site_root = tmp_path / "test-site"
        site_root.mkdir(parents=True)

        # Create existing .egregora/mkdocs.yml
        egregora_dir = site_root / ".egregora"
        egregora_dir.mkdir()
        existing_config = egregora_dir / "mkdocs.yml"
        existing_config.write_text("site_name: Existing Site\n")

        # Try to scaffold - should refuse
        config_path, created = output.scaffold_site(site_root, "New Site")

        assert not created
        assert config_path == existing_config
        # Should NOT have created posts/ directories
        assert not (site_root / "posts").exists()

    def test_scaffold_refuses_if_root_mkdocs_exists(self, tmp_path):
        """Test that scaffold refuses to init if mkdocs.yml exists at root."""
        output = output_registry.get_format("mkdocs")
        site_root = tmp_path / "test-site"
        site_root.mkdir(parents=True)

        # Create existing mkdocs.yml at root
        existing_config = site_root / "mkdocs.yml"
        existing_config.write_text("site_name: Existing Site\n")

        # Try to scaffold - should refuse
        config_path, created = output.scaffold_site(site_root, "New Site")

        assert not created
        assert config_path == existing_config
        # Should NOT have created .egregora/ directory
        assert not (site_root / ".egregora").exists()

    def test_resolve_paths(self, tmp_path):
        """Test path resolution for MkDocs site."""
        output = output_registry.get_format("mkdocs")
        site_root = tmp_path / "test-site"

        # Scaffold first
        output.scaffold_site(site_root, "Test Site")

        # Resolve paths
        config = output.resolve_paths(site_root)

        assert config.site_root == site_root
        # MODERN: docs_dir is site root (mkdocs.yml in .egregora/ with docs_dir: ..)
        assert config.docs_dir == site_root
        assert config.posts_dir.exists()
        assert config.profiles_dir.exists()
        assert config.media_dir.exists()

    def test_custom_mkdocs_config_path(self, tmp_path):
        """Test that custom mkdocs_config_path in .egregora/config.yml is respected."""
        from egregora.rendering.mkdocs_site import resolve_site_paths

        site_root = tmp_path / "test-site"
        site_root.mkdir(parents=True)

        # Create custom mkdocs.yml at custom location
        custom_config_dir = site_root / "config"
        custom_config_dir.mkdir()
        custom_mkdocs = custom_config_dir / "mkdocs.yml"
        custom_mkdocs.write_text("site_name: Custom Location\n")

        # Create .egregora/config.yml with custom path
        egregora_dir = site_root / ".egregora"
        egregora_dir.mkdir()
        config_yml = egregora_dir / "config.yml"
        config_yml.write_text("""
output:
  format: mkdocs
  mkdocs_config_path: config/mkdocs.yml
""")

        # Resolve paths - should find the custom mkdocs.yml
        site_paths = resolve_site_paths(site_root)

        # Should have found the custom mkdocs.yml
        assert site_paths.mkdocs_path == custom_mkdocs

    def test_docs_dir_resolved_relative_to_mkdocs(self, tmp_path):
        """Test that docs_dir is resolved relative to mkdocs.yml location, not site root."""
        from egregora.rendering.mkdocs_site import resolve_site_paths

        site_root = tmp_path / "test-site"
        site_root.mkdir(parents=True)

        # Create mkdocs.yml in .egregora/ with docs_dir: '..'
        egregora_dir = site_root / ".egregora"
        egregora_dir.mkdir()
        mkdocs_yml = egregora_dir / "mkdocs.yml"
        mkdocs_yml.write_text("site_name: Test\ndocs_dir: ..\n")

        # Resolve paths
        site_paths = resolve_site_paths(site_root)

        # docs_dir should be site_root (because .egregora/../ = site root)
        # NOT the parent of site_root (which would happen if resolved relative to site_root)
        assert site_paths.docs_dir == site_root
        assert site_paths.docs_dir != site_root.parent

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

        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("_chat.txt", "Test")

        # Create MkDocs site (MODERN: mkdocs.yml in .egregora/)
        site_root = tmp_path / "site"
        site_root.mkdir(parents=True, exist_ok=True)
        egregora_dir = site_root / ".egregora"
        egregora_dir.mkdir()
        (egregora_dir / "mkdocs.yml").write_text("site_name: Test\n")

        # Auto-detect
        source = input_registry.detect_source(zip_path)
        output = output_registry.detect_format(site_root)

        assert source is not None
        assert source.source_type == "whatsapp"
        assert output is not None
        assert output.format_type == "mkdocs"
