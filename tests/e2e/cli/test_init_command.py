"""Test that egregora init generates files matching the template structure.

This test ensures that the file structure created by the init/scaffolding code
matches the templates defined in src/egregora/rendering/templates/.

MODERN: Updated to use OutputAdapter abstraction instead of direct scaffolding imports.
"""

import tomllib
from pathlib import Path

from typer.testing import CliRunner

from egregora.cli.main import app
from egregora.config.settings import load_egregora_config
from egregora.output_sinks import create_default_output_registry, create_output_sink
from egregora.output_sinks.mkdocs import MkDocsAdapter
from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load

runner = CliRunner()


def test_init_on_existing_site(tmp_path: Path):
    """Verify init command handles an existing site gracefully."""
    # Run init for the first time
    result1 = runner.invoke(app, ["init", str(tmp_path)], catch_exceptions=False)
    assert result1.exit_code == 0
    assert "initialized successfully" in result1.stdout

    # Run init for the second time
    result2 = runner.invoke(app, ["init", str(tmp_path)], catch_exceptions=False)
    assert result2.exit_code == 0
    assert "site already exists" in result2.stdout


def test_init_creates_all_template_files(tmp_path: Path):
    """Verify that init creates all files defined in the templates directory."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = MkDocsAdapter()
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify expected files were created
    expected_files = [
        "README.md",
        ".gitignore",
        "docs/index.md",
        "docs/about.md",
        "docs/posts/profiles/index.md",
        "docs/posts/media/index.md",
    ]

    for expected_path in expected_files:
        output_file = tmp_path / expected_path
        assert output_file.exists(), f"Expected file '{expected_path}' was not created"


def test_init_directory_structure(tmp_path: Path):
    """Verify that init creates the correct directory structure."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = MkDocsAdapter()
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify directory structure (new structure: content at root level)
    expected_dirs = [
        "docs/posts",
        "docs/posts/profiles",
        "docs/posts/media",
        "docs/posts/media/images",
        "docs/posts/media/videos",
        "docs/posts/media/audio",
        "docs/posts/media/documents",
        "docs/posts/media/urls",
        "docs/journal",
    ]

    for dir_path in expected_dirs:
        full_path = tmp_path / dir_path
        assert full_path.is_dir(), f"Expected directory does not exist: {dir_path}"

    # Verify .gitkeep files are NOT created (cleanup)
    for subdir in ["images", "videos", "audio", "documents", "urls"]:
        gitkeep = tmp_path / "docs" / "posts" / "media" / subdir / ".gitkeep"
        assert not gitkeep.exists(), f"Unwanted .gitkeep found in media/{subdir}"

    journal_gitkeep = tmp_path / "docs" / "journal" / ".gitkeep"
    assert not journal_gitkeep.exists(), "Unwanted .gitkeep found in journal directory"


def test_egregora_directory_created(tmp_path: Path):
    """Test that .egregora/ directory is created on init."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = MkDocsAdapter()
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify .egregora/ directory exists
    egregora_dir = tmp_path / ".egregora"
    assert egregora_dir.exists(), ".egregora directory should be created"
    assert egregora_dir.is_dir(), ".egregora should be a directory"

    # Verify mkdocs.yml exists in site root
    mkdocs_yml = tmp_path / ".egregora" / "mkdocs.yml"
    assert mkdocs_yml.exists(), "mkdocs.yml should be created in .egregora/"

    # Verify config exists in site root
    config_toml = tmp_path / ".egregora.toml"
    assert config_toml.exists(), ".egregora.toml should be created"

    # Verify prompts/ directory exists
    prompts_dir = egregora_dir / "prompts"
    assert prompts_dir.exists(), ".egregora/prompts directory should be created"
    assert prompts_dir.is_dir(), ".egregora/prompts should be a directory"


def test_config_toml_structure(tmp_path: Path):
    """Test that generated .egregora.toml has correct structure."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = MkDocsAdapter()
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Load config and verify structure
    config = load_egregora_config(tmp_path)
    parsed_config = tomllib.loads((tmp_path / ".egregora.toml").read_text())

    # Verify all top-level sections exist
    assert config.models is not None
    assert config.rag is not None
    assert config.writer is not None
    assert config.privacy is not None
    assert config.enrichment is not None
    assert config.pipeline is not None
    assert config.features is not None

    # Verify some key defaults
    assert config.models.writer is not None
    assert config.rag.enabled is True
    assert "sites" in parsed_config
    assert "default" in parsed_config["sites"]


def test_mkdocs_yml_no_extra_egregora(tmp_path: Path):
    """Test that mkdocs.yml doesn't have extra.egregora."""
    # Create site
    scaffolder = MkDocsSiteScaffolder()
    scaffolder.scaffold_site(tmp_path, site_name="Egregora Archive")

    # Read mkdocs.yml from site root
    mkdocs_path = tmp_path / ".egregora" / "mkdocs.yml"
    assert mkdocs_path.exists()

    with mkdocs_path.open() as f:
        mkdocs_dict = safe_yaml_load(f.read())

    # Should NOT have extra.egregora
    extra_section = mkdocs_dict.get("extra", {})
    assert "egregora" not in extra_section, "mkdocs.yml should NOT contain extra.egregora"


def test_prompts_readme_created(tmp_path: Path):
    """Test that .egregora/prompts/README.md is created."""
    # Create and scaffold MkDocs site using OutputAdapter
    registry = create_default_output_registry()
    output_format = create_output_sink(tmp_path, format_type="mkdocs", registry=registry)
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify prompts README exists
    readme = tmp_path / ".egregora" / "prompts" / "README.md"
    assert readme.exists(), ".egregora/prompts/README.md should be created"

    # Verify it has useful content
    content = readme.read_text()
    assert "Custom Prompt" in content or "prompt" in content.lower(), (
        "README should contain information about prompts"
    )


def test_prompts_directory_populated(tmp_path: Path):
    """Test that .egregora/prompts/ contains the flattened prompt templates."""
    # Create and scaffold MkDocs site using OutputAdapter
    registry = create_default_output_registry()
    output_format = create_output_sink(tmp_path, format_type="mkdocs", registry=registry)
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify prompt files exist
    prompts_dir = tmp_path / ".egregora" / "prompts"

    expected_files = [
        "README.md",
        "writer.jinja",
        "media_detailed.jinja",
        "url_detailed.jinja",
    ]
    for filename in expected_files:
        file_path = prompts_dir / filename
        assert file_path.exists(), f".egregora/prompts/{filename} should be created"
