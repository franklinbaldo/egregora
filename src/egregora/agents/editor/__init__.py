"""Editor package for autonomous post editing with LLM agents."""

from egregora.agents.editor.document import DocumentSnapshot, Editor
from egregora.agents.editor.editor_agent import run_editor_session_with_pydantic_agent as run_editor_session

__all__ = ["DocumentSnapshot", "Editor", "run_editor_session"]
