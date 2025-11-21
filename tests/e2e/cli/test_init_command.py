"""Test that egregora init generates files matching the template structure.

This test ensures that the file structure created by the init/scaffolding code
matches the templates defined in src/egregora/rendering/templates/.

MODERN: Updated to use OutputAdapter abstraction instead of direct scaffolding imports.
"""

from pathlib import Path

from egregora.output_adapters import create_output_format


def test_init_creates_all_template_files(tmp_path: Path):
    """Verify that init creates all files defined in the templates directory."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = create_output_format(tmp_path, format_type="mkdocs")
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify expected files were created
    expected_files = [
        "README.md",
        ".gitignore",
        "docs/index.md",
        "docs/about.md",
        "docs/profiles/index.md",
        "docs/media/index.md",
    ]

    for expected_path in expected_files:
        output_file = tmp_path / expected_path
        assert output_file.exists(), f"Expected file '{expected_path}' was not created"


def test_init_directory_structure(tmp_path: Path):
    """Verify that init creates the correct directory structure."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = create_output_format(tmp_path, format_type="mkdocs")
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify directory structure (new structure: content at root level)
    expected_dirs = [
        "docs/posts",
        "docs/profiles",
        "docs/media",
        "docs/media/images",
        "docs/media/videos",
        "docs/media/audio",
        "docs/media/documents",
        "docs/posts/journal",
    ]

    for dir_path in expected_dirs:
        full_path = tmp_path / dir_path
        assert full_path.is_dir(), f"Expected directory does not exist: {dir_path}"

    # Verify .gitkeep files in media subdirectories
    for subdir in ["images", "videos", "audio", "documents"]:
        gitkeep = tmp_path / "docs" / "media" / subdir / ".gitkeep"
        assert gitkeep.exists(), f".gitkeep missing in media/{subdir}"


def test_egregora_directory_created(tmp_path: Path):
    """Test that .egregora/ directory is created on init."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = create_output_format(tmp_path, format_type="mkdocs")
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify .egregora/ directory exists
    egregora_dir = tmp_path / ".egregora"
    assert egregora_dir.exists(), ".egregora directory should be created"
    assert egregora_dir.is_dir(), ".egregora should be a directory"

    # Verify mkdocs.yml exists in .egregora/
    mkdocs_yml = egregora_dir / "mkdocs.yml"
    assert mkdocs_yml.exists(), ".egregora/mkdocs.yml should be created"

    # Verify config.yml exists
    config_yml = egregora_dir / "config.yml"
    assert config_yml.exists(), ".egregora/config.yml should be created"

    # Verify prompts/ directory exists
    prompts_dir = egregora_dir / "prompts"
    assert prompts_dir.exists(), ".egregora/prompts directory should be created"
    assert prompts_dir.is_dir(), ".egregora/prompts should be a directory"


def test_config_yml_structure(tmp_path: Path):
    """Test that generated config.yml has correct structure."""
    from egregora.config.settings import load_egregora_config

    # Create and scaffold MkDocs site using OutputAdapter
    output_format = create_output_format(tmp_path, format_type="mkdocs")
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Load config and verify structure
    config = load_egregora_config(tmp_path)

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


def test_mkdocs_yml_no_extra_egregora(tmp_path: Path):
    """Test that mkdocs.yml doesn't have extra.egregora."""
    import yaml

    from egregora.init.scaffolding import ensure_mkdocs_project
    from egregora.output_adapters.mkdocs.adapter import _ConfigLoader

    # Create site
    ensure_mkdocs_project(tmp_path)

    # Read mkdocs.yml from .egregora/
    mkdocs_path = tmp_path / ".egregora" / "mkdocs.yml"
    assert mkdocs_path.exists()

    with mkdocs_path.open() as f:
        mkdocs_dict = yaml.load(f, Loader=_ConfigLoader)

    # Should NOT have extra.egregora
    extra_section = mkdocs_dict.get("extra", {})
    assert "egregora" not in extra_section, (
        "mkdocs.yml should NOT contain extra.egregora (config moved to .egregora/config.yml)"
    )


def test_prompts_readme_created(tmp_path: Path):
    """Test that .egregora/prompts/README.md is created."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = create_output_format(tmp_path, format_type="mkdocs")
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


def test_prompts_subdirectories_created(tmp_path: Path):
    """Test that .egregora/prompts/ subdirectories are created."""
    # Create and scaffold MkDocs site using OutputAdapter
    output_format = create_output_format(tmp_path, format_type="mkdocs")
    _mkdocs_path, created = output_format.scaffold_site(tmp_path, site_name="Test Site")

    # Verify site was created
    assert created

    # Verify subdirectories exist
    prompts_dir = tmp_path / ".egregora" / "prompts"

    system_dir = prompts_dir / "system"
    assert system_dir.exists(), ".egregora/prompts/system should be created"
    assert system_dir.is_dir(), ".egregora/prompts/system should be a directory"

    enrichment_dir = prompts_dir / "enrichment"
    assert enrichment_dir.exists(), ".egregora/prompts/enrichment should be created"
    assert enrichment_dir.is_dir(), ".egregora/prompts/enrichment should be a directory"
