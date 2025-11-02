"""Editor package for autonomous post editing with LLM agents."""

from egregora.generation.editor.agent import run_editor_session
from egregora.generation.editor.document import DocumentSnapshot, Editor

__all__ = [
    "run_editor_session",
    "DocumentSnapshot",
    "Editor",
]
