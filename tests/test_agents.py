from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from src.egregora.agents.loader import load_agent
from src.egregora.agents.registry import ToolRegistry, SkillRegistry
from src.egregora.agents.resolver import AgentResolver
from src.egregora.orchestration.cli import app

runner = CliRunner()

@pytest.fixture(scope="module")
def temp_site_path(tmp_path_factory):
    """Creates a temporary site structure for testing."""
    site_path = tmp_path_factory.mktemp("site")
    egregora_path = site_path / ".egregora"
    (egregora_path / "agents").mkdir(parents=True)
    (egregora_path / "tools").mkdir()
    (egregora_path / "skills").mkdir()

    # Create dummy agent files
    (egregora_path / "agents" / "_default.jinja").write_text(
        """{#---
agent_id: default_v1
model: default_model
seed: 42
variables:
  defaults: { max_tokens: 100 }
  allowed: [max_tokens]
tools:
  use_profiles: [minimal]
skills:
  enable: []
#---#}
Default prompt."""
    )
    (egregora_path / "agents" / "curator.jinja").write_text(
        """{#---
agent_id: curator_v1
model: curator_model
seed: 1337
variables:
  defaults: { max_tokens: 200 }
  allowed: [max_tokens, site_name]
tools:
  use_profiles: [minimal]
  allow: [tool_b]
skills:
  enable: [skill_a]
#---#}
Curator prompt."""
    )

    # Create dummy tool files
    (egregora_path / "tools" / "profiles.yaml").write_text(
        "profiles:\n  minimal:\n    allow: [tool_a]\n    deny: [tool_c]"
    )
    (egregora_path / "tools" / "tool_a.yaml").write_text("id: tool_a\nkind: local")
    (egregora_path / "tools" / "tool_b.yaml").write_text("id: tool_b\nkind: local")

    # Create dummy skill files
    (egregora_path / "skills" / "skill_a.md").write_text("This is skill A.")
    (egregora_path / "skills" / "skill_b.jinja").write_text("{% macro test() %}Test{% endmacro %}")

    # Create dummy docs structure
    docs_path = site_path / "docs"
    (docs_path / "posts").mkdir(parents=True)
    (docs_path / "posts" / "post_with_agent.md").write_text(
        "---\negregora:\n  agent: curator\n---\nPost content."
    )
    (docs_path / "posts" / "post_without_agent.md").write_text("Post content.")
    (docs_path / "other_posts").mkdir(parents=True)
    (docs_path / "other_posts" / "another_post.md").write_text("Another post.")
    (docs_path / "_agent.md").write_text("---\negregora:\n  agent: _default\n---")

    return site_path


def test_load_agent(temp_site_path):
    """Test loading an agent from a .jinja file."""
    agent_config = load_agent("curator", temp_site_path / ".egregora")
    assert agent_config.agent_id == "curator_v1"
    assert agent_config.model == "curator_model"
    assert "Curator prompt." in agent_config.prompt_template

def test_tool_registry(temp_site_path):
    """Test tool registry functionality."""
    registry = ToolRegistry(temp_site_path / ".egregora")
    agent_config = load_agent("curator", temp_site_path / ".egregora")
    toolset = registry.resolve_toolset(agent_config.tools)
    assert toolset == {"tool_a", "tool_b"}
    assert registry.get_toolset_hash(toolset) is not None

def test_skill_registry(temp_site_path):
    """Test skill registry functionality."""
    registry = SkillRegistry(temp_site_path / ".egregora")
    agent_config = load_agent("curator", temp_site_path / ".egregora")
    skills = agent_config.skills.get("enable", [])
    assert "skill_a" in skills
    assert registry.get_skillset_hash(skills) is not None

def test_agent_resolver(temp_site_path):
    """Test agent resolver precedence."""
    resolver = AgentResolver(temp_site_path / ".egregora", temp_site_path / "docs")

    # Test post-specific agent
    post_path = temp_site_path / "docs" / "posts" / "post_with_agent.md"
    agent_config, _ = resolver.resolve(post_path)
    assert agent_config.agent_id == "curator_v1"

    # Test section override
    post_path = temp_site_path / "docs" / "posts" / "post_without_agent.md"
    agent_config, _ = resolver.resolve(post_path)
    assert agent_config.agent_id == "default_v1"

    # Test fallback to default
    post_path = temp_site_path / "docs" / "other_posts" / "another_post.md"
    agent_config, _ = resolver.resolve(post_path)
    assert agent_config.agent_id == "default_v1"


def test_cli_agents_list(temp_site_path):
    """Test the 'egregora agents list' command."""
    result = runner.invoke(app, ["agents", "list", "--site-dir", str(temp_site_path)])
    assert result.exit_code == 0
    assert "curator" in result.stdout
    assert "_default" in result.stdout

def test_cli_agents_explain(temp_site_path):
    """Test the 'egregora agents explain' command."""
    result = runner.invoke(app, ["agents", "explain", "curator", "--site-dir", str(temp_site_path)])
    assert result.exit_code == 0
    assert "curator_v1" in result.stdout
    assert "tool_a" in result.stdout
    assert "skill_a" in result.stdout

def test_cli_agents_lint(temp_site_path):
    """Test the 'egregora agents lint' command."""
    result = runner.invoke(app, ["agents", "lint", "--site-dir", str(temp_site_path)])
    assert result.exit_code == 0
    assert "All agents, tools, and skills are valid" in result.stdout
