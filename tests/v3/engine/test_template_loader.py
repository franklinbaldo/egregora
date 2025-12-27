"""Tests for the V3 template loader."""

from pathlib import Path

from egregora_v3.engine.template_loader import TemplateLoader


def test_template_loader_finds_default_template_dir() -> None:
    """Verify TemplateLoader finds the default template directory."""
    # WHEN
    loader = TemplateLoader()

    # THEN
    assert loader.template_dir is not None
    assert isinstance(loader.template_dir, Path)
    assert loader.template_dir.exists()
    assert loader.template_dir.name == "prompts"
    assert "egregora_v3" in str(loader.template_dir)
