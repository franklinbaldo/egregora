"""Prompt templates used by the profile updater."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

__all__ = [
    "UPDATE_DECISION_PROMPT",
    "PROFILE_REWRITE_PROMPT",
    "PROFILE_APPEND_PROMPT",
]

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompt_templates"


def _load_prompt(filename: str) -> str:
    local_path = _PROMPTS_DIR / filename
    if local_path.exists():
        return local_path.read_text(encoding="utf-8").strip()

    return (
        resources.files(__package__)
        .joinpath(f"prompt_templates/{filename}")
        .read_text(encoding="utf-8")
        .strip()
    )


UPDATE_DECISION_PROMPT = _load_prompt("update_decision_prompt.md")
PROFILE_REWRITE_PROMPT = _load_prompt("profile_rewrite_prompt.md")
PROFILE_APPEND_PROMPT = _load_prompt("profile_append_prompt.md")
