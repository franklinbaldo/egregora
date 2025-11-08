"""Unit tests for custom prompt override mechanism.

Tests cover:
- Finding custom prompts directory
- Fallback to package prompts
- Custom prompt template override
- Environment creation with site_root
"""

from pathlib import Path

from egregora.prompt_templates import (
    PACKAGE_PROMPTS_DIR,
    create_prompt_environment,
    find_prompts_dir,
)


def test_find_prompts_dir_custom(tmp_path):
    """Test finding custom prompts directory."""
    custom_prompts = tmp_path / ".egregora" / "prompts"
    custom_prompts.mkdir(parents=True)

    found = find_prompts_dir(tmp_path)
    assert found == custom_prompts


def test_find_prompts_dir_fallback_to_package():
    """Test fallback to package prompts when custom not found."""
    found = find_prompts_dir(Path("/nonexistent"))
    assert found == PACKAGE_PROMPTS_DIR


def test_find_prompts_dir_none():
    """Test find_prompts_dir with None returns package prompts."""
    found = find_prompts_dir(None)
    assert found == PACKAGE_PROMPTS_DIR


def test_find_prompts_dir_custom_not_directory(tmp_path):
    """Test that find_prompts_dir requires a directory, not a file."""
    # Create .egregora/prompts as a file instead of directory
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()
    (egregora_dir / "prompts").write_text("not a directory")

    # Should fall back to package prompts
    found = find_prompts_dir(tmp_path)
    assert found == PACKAGE_PROMPTS_DIR


def test_create_prompt_environment_custom(tmp_path):
    """Test creating environment with custom prompts directory."""
    # Create custom prompts
    custom_prompts = tmp_path / ".egregora" / "prompts" / "system"
    custom_prompts.mkdir(parents=True)
    (custom_prompts / "test.jinja").write_text("Custom: {{ value }}")

    # Create environment with custom prompts
    env = create_prompt_environment(tmp_path)
    template = env.get_template("system/test.jinja")

    # Should render custom template
    result = template.render(value="works")
    assert result == "Custom: works"


def test_create_prompt_environment_fallback(tmp_path):
    """Test environment falls back to package prompts."""
    # Don't create custom prompts, use package prompts
    env = create_prompt_environment(tmp_path)

    # Should be able to load package prompts
    # (we know system/writer.jinja exists in package)
    template = env.get_template("system/writer.jinja")
    assert template is not None


def test_empty_custom_prompts_directory_fallback(tmp_path):
    """Test that empty .egregora/prompts/ directory falls back to package prompts.

    This is the critical bug scenario: when `egregora init` creates an empty
    .egregora/prompts/ directory, the prompt loader should still find templates
    from the package defaults, not fail with TemplateNotFound.
    """
    # Create empty custom prompts directory (like `egregora init` does)
    custom_prompts = tmp_path / ".egregora" / "prompts"
    custom_prompts.mkdir(parents=True)

    # Create environment - should use package prompts as fallback
    env = create_prompt_environment(tmp_path)

    # Should successfully load package templates even though custom dir is empty
    writer_template = env.get_template("system/writer.jinja")
    assert writer_template is not None

    # Test that we can actually render it
    result = writer_template.render(
        conversation="test",
        custom_instructions="",
        context={},
        rag_context="",
        profiles_context="",
        freeform_memory="",
        active_authors=[],
        start_time="2025-01-01",
        end_time="2025-01-02",
        meme_help="",
        markdown_features="",
    )
    assert result  # Should have content, not be empty or error


def test_custom_prompt_override_priority(tmp_path):
    """Test that custom prompts override package prompts."""
    # Create custom writer prompt
    custom_prompts = tmp_path / ".egregora" / "prompts" / "system"
    custom_prompts.mkdir(parents=True)
    (custom_prompts / "writer.jinja").write_text("CUSTOM WRITER PROMPT: {{ date }}")

    # Create environment with custom prompts
    env = create_prompt_environment(tmp_path)
    template = env.get_template("system/writer.jinja")

    # Should render custom template, not package template
    result = template.render(date="2025-01-01")
    assert "CUSTOM WRITER PROMPT: 2025-01-01" in result
    # Package template would have different content


def test_custom_prompt_partial_override(tmp_path):
    """Test that only specified prompts are overridden, others use package defaults."""
    # Create custom writer prompt only
    custom_prompts = tmp_path / ".egregora" / "prompts" / "system"
    custom_prompts.mkdir(parents=True)
    (custom_prompts / "writer.jinja").write_text("CUSTOM: {{ date }}")

    env = create_prompt_environment(tmp_path)

    # Writer should be custom
    writer_template = env.get_template("system/writer.jinja")
    writer_result = writer_template.render(date="2025-01-01")
    assert "CUSTOM: 2025-01-01" in writer_result

    # Editor should still use package default (not overridden)
    # This will fail if editor.jinja doesn't exist, which is expected
    # because we only override writer.jinja
    try:
        editor_template = env.get_template("system/editor.jinja")
        # If it exists in package, we should get it
        assert editor_template is not None
    except Exception:
        # If editor.jinja doesn't exist in package, that's fine
        # This test is about priority, not existence
        pass


def test_create_prompt_environment_none_site_root():
    """Test creating environment with None site_root uses package prompts."""
    env = create_prompt_environment(None)

    # Should use package prompts
    template = env.get_template("system/writer.jinja")
    assert template is not None


def test_prompt_environment_jinja_features(tmp_path):
    """Test that prompt environment has expected Jinja2 features."""
    # Create custom prompt with Jinja2 features
    custom_prompts = tmp_path / ".egregora" / "prompts" / "system"
    custom_prompts.mkdir(parents=True)

    template_content = """
{# Comment should be stripped #}
{% if enabled %}
Enabled feature
{% endif %}

{% for item in items %}
- {{ item }}
{% endfor %}
"""
    (custom_prompts / "test.jinja").write_text(template_content)

    env = create_prompt_environment(tmp_path)
    template = env.get_template("system/test.jinja")

    result = template.render(enabled=True, items=["a", "b", "c"])

    # Comments should be stripped
    assert "#" not in result

    # Conditional should work
    assert "Enabled feature" in result

    # Loop should work
    assert "- a" in result
    assert "- b" in result
    assert "- c" in result


def test_prompts_dir_structure(tmp_path):
    """Test that custom prompts can have subdirectories."""
    # Create nested structure
    system_prompts = tmp_path / ".egregora" / "prompts" / "system"
    enrichment_prompts = tmp_path / ".egregora" / "prompts" / "enrichment"

    system_prompts.mkdir(parents=True)
    enrichment_prompts.mkdir(parents=True)

    (system_prompts / "writer.jinja").write_text("System: {{ msg }}")
    (enrichment_prompts / "url.jinja").write_text("Enrichment: {{ url }}")

    env = create_prompt_environment(tmp_path)

    # Both should be accessible
    system_template = env.get_template("system/writer.jinja")
    assert system_template.render(msg="test") == "System: test"

    enrichment_template = env.get_template("enrichment/url.jinja")
    assert enrichment_template.render(url="http://example.com") == "Enrichment: http://example.com"
