"""Editor package for autonomous post editing with LLM agents."""

from egregora.agents.editor.agent import run_editor_session_with_pydantic_agent as run_editor_session
from egregora.agents.editor.document import DocumentSnapshot, Editor

__all__ = ["DocumentSnapshot", "Editor", "run_editor_session"]
