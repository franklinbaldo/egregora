"""Test that egregora init generates files matching the template structure.

This test ensures that the file structure created by the init/scaffolding code
matches the templates defined in src/egregora/rendering/templates/.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.config.site import resolve_site_paths
from egregora.init.scaffolding import SITE_TEMPLATES_DIR, _create_site_structure


def test_init_creates_all_template_files(tmp_path: Path):
    """Verify that init creates all files defined in the templates directory."""
    # Create a minimal mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test\ndocs_dir: docs\n", encoding="utf-8")

    # Resolve site paths
    site_paths = resolve_site_paths(tmp_path)

    # Set up Jinja2 environment
    template_dir = SITE_TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Create site structure
    context = {
        "site_name": "Test Site",
        "site_url": "https://example.com",
        "repo_url": "",
        "blog_dir": "posts",
    }
    _create_site_structure(site_paths, env, context)

    # Define expected template → output file mapping
    # Format: {template_name: output_path_relative_to_site_root}
    expected_files = {
        "README.md.jinja2": "README.md",
        "gitignore.jinja2": ".gitignore",
        "homepage.md.jinja2": "docs/index.md",
        "about.md.jinja2": "docs/about.md",
        "profiles_index.md.jinja2": "docs/profiles/index.md",
        "media_index.md.jinja2": "docs/media/index.md",
    }

    # Verify each template has a corresponding output file
    for template_name, expected_path in expected_files.items():
        output_file = tmp_path / expected_path
        assert output_file.exists(), (
            f"Template '{template_name}' should generate file at '{expected_path}', but file does not exist"
        )

    # Verify blog index (not from template, but created by scaffolding)
    blog_index = tmp_path / "docs" / "index.md"
    assert blog_index.exists(), "Blog index should be created in docs/index.md"


def test_all_templates_are_used(tmp_path: Path):
    """Verify that every .jinja template in templates/ is used by init."""
    # Get all templates
    template_dir = SITE_TEMPLATES_DIR
    all_templates = set(template_dir.glob("*.jinja"))

    # Templates that should be used by _create_site_structure
    used_templates = {
        template_dir / "README.md.jinja",
        template_dir / ".gitignore.jinja",
        template_dir / "media_index.md.jinja",
    }

    # Templates that are used elsewhere (not in _create_site_structure)
    other_templates = {
        template_dir / "mkdocs.yml.jinja",  # Used in _create_default_mkdocs
    }

    # Verify all templates are accounted for
    expected_templates = used_templates | other_templates
    actual_templates = all_templates

    missing = actual_templates - expected_templates
    extra = expected_templates - actual_templates

    assert not missing, (
        f"Found templates that are not accounted for in the test: {[t.name for t in missing]}. "
        f"Either add them to used_templates or other_templates, or remove them from the codebase."
    )

    assert not extra, (
        f"Test expects templates that don't exist: {[t.name for t in extra]}. "
        f"Update the test to match the actual templates in {template_dir}"
    )


def test_init_directory_structure(tmp_path: Path):
    """Verify that init creates the correct directory structure."""
    # Create a minimal mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test\ndocs_dir: docs\n", encoding="utf-8")

    # Resolve site paths
    site_paths = resolve_site_paths(tmp_path)

    # Set up Jinja2 environment
    template_dir = SITE_TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Create site structure
    context = {
        "site_name": "Test Site",
        "site_url": "https://example.com",
        "repo_url": "",
        "blog_dir": "posts",
    }
    _create_site_structure(site_paths, env, context)

    # Verify directory structure
    expected_dirs = [
        "docs",
        "docs/posts",
        "docs/profiles",
        "docs/media",
        "docs/media/images",
        "docs/media/videos",
        "docs/media/audio",
        "docs/media/documents",
    ]

    for dir_path in expected_dirs:
        full_path = tmp_path / dir_path
        assert full_path.is_dir(), f"Expected directory does not exist: {dir_path}"

    # Verify .gitkeep files in media subdirectories
    for subdir in ["images", "videos", "audio", "documents"]:
        gitkeep = tmp_path / "docs" / "media" / subdir / ".gitkeep"
        assert gitkeep.exists(), f".gitkeep missing in docs/media/{subdir}"


def test_template_files_match_output_structure():
    """Verify template filenames match their output paths logically."""
    # This is a sanity check to ensure template names make sense
    template_dir = SITE_TEMPLATES_DIR

    # Expected logical mapping (not exhaustive, just key examples)
    # Templates are in root of site template directory
    mappings = {
        "README.md.jinja": "README.md",
        ".gitignore.jinja": ".gitignore",
        "media_index.md.jinja": "docs/media/index.md",  # Semantic name: media_index
        "mkdocs.yml.jinja": "mkdocs.yml",
    }

    # Templates with semantic names (don't check name correspondence)
    semantic_names = {"media_index.md.jinja"}

    for template_name, expected_output in mappings.items():
        template_path = template_dir / template_name
        assert template_path.exists(), f"Expected template '{template_name}' does not exist in {template_dir}"

        # Verify the template name makes sense for the output
        # Skip semantic name checks (homepage is a valid semantic name for index.md)
        if template_name in semantic_names:
            continue

        # This is just checking the naming convention is sensible
        if expected_output == ".gitignore":
            assert "gitignore" in template_name.lower()
        else:
            base_name = expected_output.replace(".md", "").replace(".yml", "").lower()
            assert base_name in template_name.lower(), (
                f"Template '{template_name}' should contain '{base_name}' in its name"
            )


def test_egregora_directory_created(tmp_path: Path):
    """Test that .egregora/ directory is created on init."""
    # Create a minimal mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test\ndocs_dir: docs\n", encoding="utf-8")

    # Resolve site paths
    site_paths = resolve_site_paths(tmp_path)

    # Set up Jinja2 environment
    template_dir = SITE_TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Create site structure
    context = {
        "site_name": "Test Site",
        "site_url": "https://example.com",
        "repo_url": "",
        "blog_dir": "posts",
    }
    _create_site_structure(site_paths, env, context)

    # Verify .egregora/ directory exists
    egregora_dir = tmp_path / ".egregora"
    assert egregora_dir.exists(), ".egregora directory should be created"
    assert egregora_dir.is_dir(), ".egregora should be a directory"

    # Verify config.yml exists
    config_yml = egregora_dir / "config.yml"
    assert config_yml.exists(), ".egregora/config.yml should be created"

    # Verify prompts/ directory exists
    prompts_dir = egregora_dir / "prompts"
    assert prompts_dir.exists(), ".egregora/prompts directory should be created"
    assert prompts_dir.is_dir(), ".egregora/prompts should be a directory"


def test_config_yml_structure(tmp_path: Path):
    """Test that generated config.yml has correct structure."""
    from egregora.config.loader import load_egregora_config

    # Create a minimal mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test\ndocs_dir: docs\n", encoding="utf-8")

    # Resolve site paths
    site_paths = resolve_site_paths(tmp_path)

    # Set up Jinja2 environment
    template_dir = SITE_TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Create site structure
    context = {
        "site_name": "Test Site",
        "site_url": "https://example.com",
        "repo_url": "",
        "blog_dir": "posts",
    }
    _create_site_structure(site_paths, env, context)

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

    from egregora.config.site import _ConfigLoader
    from egregora.init.scaffolding import ensure_mkdocs_project

    # Create site
    ensure_mkdocs_project(tmp_path)

    # Read mkdocs.yml
    mkdocs_path = tmp_path / "mkdocs.yml"
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
    # Create a minimal mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test\ndocs_dir: docs\n", encoding="utf-8")

    # Resolve site paths
    site_paths = resolve_site_paths(tmp_path)

    # Set up Jinja2 environment
    template_dir = SITE_TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Create site structure
    context = {
        "site_name": "Test Site",
        "site_url": "https://example.com",
        "repo_url": "",
        "blog_dir": "posts",
    }
    _create_site_structure(site_paths, env, context)

    # Verify prompts README exists
    readme = tmp_path / ".egregora" / "prompts" / "README.md"
    assert readme.exists(), ".egregora/prompts/README.md should be created"

    # Verify it has useful content
    content = readme.read_text()
    assert "Custom Prompt Overrides" in content or "prompt" in content.lower(), (
        "README should contain information about prompts"
    )


def test_prompts_subdirectories_created(tmp_path: Path):
    """Test that .egregora/prompts/ subdirectories are created."""
    # Create a minimal mkdocs.yml
    mkdocs_yml = tmp_path / "mkdocs.yml"
    mkdocs_yml.write_text("site_name: Test\ndocs_dir: docs\n", encoding="utf-8")

    # Resolve site paths
    site_paths = resolve_site_paths(tmp_path)

    # Set up Jinja2 environment
    template_dir = SITE_TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Create site structure
    context = {
        "site_name": "Test Site",
        "site_url": "https://example.com",
        "repo_url": "",
        "blog_dir": "posts",
    }
    _create_site_structure(site_paths, env, context)

    # Verify subdirectories exist
    prompts_dir = tmp_path / ".egregora" / "prompts"

    system_dir = prompts_dir / "system"
    assert system_dir.exists(), ".egregora/prompts/system should be created"
    assert system_dir.is_dir(), ".egregora/prompts/system should be a directory"

    enrichment_dir = prompts_dir / "enrichment"
    assert enrichment_dir.exists(), ".egregora/prompts/enrichment should be created"
    assert enrichment_dir.is_dir(), ".egregora/prompts/enrichment should be a directory"
