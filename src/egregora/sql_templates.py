"""Utilities for rendering SQL DDL templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "sql"


@lru_cache(maxsize=1)
def _get_environment() -> Environment:
    """Return a cached Jinja environment for SQL templates."""

    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_sql_template(template_name: str, /, **context: Any) -> str:
    """Render the SQL template ``template_name`` with ``context`` values."""

    environment = _get_environment()
    template = environment.get_template(template_name)
    return template.render(**context)
