import pytest

from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder, safe_yaml_load


def test_yaml_injection_in_site_name(tmp_path):
    """Verify that site_name is properly escaped in mkdocs.yml to prevent YAML injection."""
    scaffolder = MkDocsSiteScaffolder()

    # Malicious site name trying to inject a new key 'injected_key: true'
    # The payload attempts to break out of the 'site_name' value
    malicious_site_name = "Safe Name\ninjected_key: true"

    # Scaffold the site
    mkdocs_path, _ = scaffolder.scaffold_site(tmp_path, malicious_site_name)

    # Read and parse the generated mkdocs.yml
    content = mkdocs_path.read_text(encoding="utf-8")
    parsed_yaml = safe_yaml_load(content)

    # Check if injection was successful
    # If successful, 'injected_key' will be a top-level key in the parsed YAML
    # If properly escaped/quoted, it should be part of the 'site_name' string

    # We expect 'injected_key' NOT to be in the top-level keys
    if "injected_key" in parsed_yaml:
        pytest.fail(
            f"YAML Injection successful! 'injected_key' found in top-level YAML keys.\nContent:\n{content}"
        )

    # Ensure the site_name contains the full string (including newline)
    assert parsed_yaml["site_name"] == malicious_site_name
