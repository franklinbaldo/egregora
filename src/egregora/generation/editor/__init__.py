"""Editor package for autonomous post editing with LLM agents."""

from egregora.generation.editor.document import DocumentSnapshot, Editor
from egregora.generation.editor.pydantic_agent import (
    run_editor_session_with_pydantic_agent as run_editor_session,
)

__all__ = [
    "run_editor_session",
    "DocumentSnapshot",
    "Editor",
]
