import pytest

from egregora.agents.registry import ToolRegistry, ToolRegistryError


def _write_profiles(tmp_path, content: str) -> str:
    egregora_path = tmp_path / ".egregora"
    tools_dir = egregora_path / "tools"
    tools_dir.mkdir(parents=True)
    profiles_path = tools_dir / "profiles.yaml"
    profiles_path.write_text(content, encoding="utf-8")
    return egregora_path


def test_profiles_raise_for_non_mapping_profile(tmp_path):
    egregora_path = _write_profiles(
        tmp_path,
        """
profiles:
  default: []
""",
    )

    with pytest.raises(ToolRegistryError, match=r"default.*mapping"):
        ToolRegistry(egregora_path)


def test_profiles_raise_for_non_sequence_allow_or_deny(tmp_path):
    egregora_path = _write_profiles(
        tmp_path,
        """
profiles:
  default:
    allow: tool-1
    deny: tool-2
""",
    )

    with pytest.raises(ToolRegistryError, match=r"allow.*list|sequence"):
        ToolRegistry(egregora_path)
