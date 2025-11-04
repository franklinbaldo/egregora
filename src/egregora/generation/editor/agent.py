import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic_ai import Agent

from ...agents.registry import ToolRegistry
from ...agents.resolver import AgentResolver
from ...agents.tools import AVAILABLE_TOOLS
from ...config import ModelConfig
from .document import DocumentSnapshot, Editor

logger = logging.getLogger(__name__)

@dataclass
class EditorResult:
    """Result of an editor session."""
    final_content: str
    decision: str
    notes: str
    edits_made: bool
    tool_calls: list[dict[str, Any]]
    agent_hash: str
    toolset_hash: str
    skillset_hash: str
    prompt_render_hash: str

def markdown_to_snapshot(content: str, doc_id: str) -> DocumentSnapshot:
    """Convert markdown content to DocumentSnapshot."""
    lines = content.split("\n")
    return DocumentSnapshot(
        doc_id=doc_id, version=1, meta={}, lines={i: line for i, line in enumerate(lines)}
    )

def snapshot_to_markdown(snapshot: DocumentSnapshot) -> str:
    """Convert DocumentSnapshot back to markdown."""
    sorted_lines = [snapshot.lines[i] for i in sorted(snapshot.lines.keys())]
    return "\n".join(sorted_lines)

async def run_editor_session(
    post_path: Path,
    model_config: ModelConfig,
    egregora_path: Path,
    docs_path: Path,
    rag_dir: Path,
    client: genai.Client,
    context: dict[str, Any] | None = None,
    agent_override: str | None = None,
) -> EditorResult:
    """
    Run a full editing session on a post using a pydantic-ai agent.
    """
    if not post_path.exists():
        raise FileNotFoundError(f"Post not found: {post_path}")

    original_content = post_path.read_text(encoding="utf-8")
    snapshot = markdown_to_snapshot(original_content, doc_id=str(post_path))
    editor = Editor(snapshot)

    resolver = AgentResolver(egregora_path, docs_path)
    tool_registry = ToolRegistry(egregora_path)
    jinja_env = SandboxedEnvironment(
        loader=FileSystemLoader(str(egregora_path)),
        autoescape=True,
    )

    agent_config, prompt_template, final_vars = resolver.resolve(post_path, agent_override)

    render_context = final_vars.copy()
    render_context.update({
        "doc_id": str(post_path),
        "version": snapshot.version,
        "lines": snapshot.lines,
        "context": context or {},
        "env": agent_config.env
    })

    template = jinja_env.from_string(prompt_template)
    prompt = template.render(render_context)

    enabled_tool_names = tool_registry.resolve_toolset(agent_config.tools)
    tools = [AVAILABLE_TOOLS[name] for name in enabled_tool_names if name in AVAILABLE_TOOLS]

    agent_hash = tool_registry.get_agent_hash(agent_config, prompt_template)
    toolset_hash = tool_registry.get_toolset_hash(enabled_tool_names)
    skillset_hash = tool_registry.get_skillset_hash(agent_config.skills.enable)
    prompt_render_hash = hashlib.sha256(prompt.encode()).hexdigest()

    dependencies = {
        "editor": editor,
        "client": client,
        "model_config": model_config,
        "rag_dir": rag_dir,
    }

    agent = Agent(
        agent_config.model,
        system_prompt=prompt,
        tools=tools,
        dependencies=dependencies,
        output_type=FinishResult,
    )

    try:
        result = await agent.run()
    except Exception as e:
        logger.error(f"Agent session failed: {e}")
        return EditorResult(
            final_content=snapshot_to_markdown(editor.snapshot),
            decision="hold",
            notes=f"Agent session failed: {e}",
            edits_made=editor.snapshot.version > 1,
            tool_calls=[],
            agent_hash=agent_hash,
            toolset_hash=toolset_hash,
            skillset_hash=skillset_hash,
            prompt_render_hash=prompt_render_hash,
        )

    return EditorResult(
        final_content=snapshot_to_markdown(editor.snapshot),
        decision=result.output.decision,
        notes=result.output.notes,
        edits_made=editor.snapshot.version > 1,
        tool_calls=result.tool_calls,
        agent_hash=agent_hash,
        toolset_hash=toolset_hash,
        skillset_hash=skillset_hash,
        prompt_render_hash=prompt_render_hash,
    )
