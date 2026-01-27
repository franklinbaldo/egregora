from __future__ import annotations

from egregora.output_sinks.mkdocs.scaffolding import safe_yaml_load


def test_safe_yaml_load_prevents_arbitrary_code_execution():
    """Verify that safe_yaml_load does not execute arbitrary code."""
    # This payload attempts to execute a command via the yaml.load exploit.
    # If the fix is correct, this should be parsed as a string or ignored, not executed.
    malicious_payload = "!!python/object/apply:os.system ['echo vulnerable']"

    # safe_yaml_load uses a custom loader that intentionally swallows unknown tags
    # (like !!python/object...) and returns None, which defaults to {}
    result = safe_yaml_load(malicious_payload)

    # Verify it didn't execute and didn't return the malicious object
    assert result == {}


def test_safe_yaml_load_handles_regular_yaml():
    """Verify that safe_yaml_load still parses regular YAML correctly."""
    yaml_content = """
    site_name: My Docs
    nav:
        - Home: index.md
        - About: about.md
    """
    result = safe_yaml_load(yaml_content)
    assert isinstance(result, dict)
    assert result["site_name"] == "My Docs"
    assert len(result["nav"]) == 2
