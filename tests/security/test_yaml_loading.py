from __future__ import annotations

import pytest

from egregora.output_adapters.mkdocs.scaffolding import safe_yaml_load


def test_safe_yaml_load_prevents_arbitrary_code_execution():
    """Verify that safe_yaml_load does not execute arbitrary code."""
    # This payload attempts to execute a command via the yaml.load exploit.
    # If the fix is correct, this should be parsed as a string, not executed.
    malicious_payload = "!!python/object/apply:os.system ['echo vulnerable']"

    # The safe_yaml_load function should raise a ConstructorError because
    # it doesn't know how to construct the malicious object. This is the
    # expected, safe behavior.
    with pytest.raises(Exception):
        safe_yaml_load(malicious_payload)


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
