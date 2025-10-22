"""Function calling tools for LLM-driven post generation."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from google.genai import types
    except ModuleNotFoundError:
        types = None  # type: ignore[misc]
else:
    try:
        from google.genai import types
    except ModuleNotFoundError:
        types = None


def get_write_post_declaration():  # type: ignore[no-untyped-def]
    """Return the function declaration for write_post tool."""
    if types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada. "
            "Instale-a para usar ferramentas (ex.: `pip install google-genai`)."
        )

    return types.FunctionDeclaration(
        name="write_post",
        description=(
            "Escreve um post individual sobre um fio de conversa específico. "
            "Use esta ferramenta para cada thread/fio distinto que você identificar no transcrito. "
            "Crie múltiplos posts separados em vez de um único post diário."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título do fio (ex: 'A Pacificação Social')",
                },
                "slug": {
                    "type": "string",
                    "description": (
                        "URL-friendly slug derivado do título (ex: 'pacificacao-social'). "
                        "Use apenas letras minúsculas, números e hífens. "
                        "Máximo 50 caracteres. "
                        "Exemplos: 'frameworks-vs-simplicidade', 'debate-velocidade-qualidade', 'ia-artigo-shared'"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": (
                        "Conteúdo markdown completo do post incluindo front matter YAML, "
                        "corpo do texto, e referências a participantes. "
                        "DEVE incluir o front matter no formato:\n"
                        "---\n"
                        "date: YYYY-MM-DD\n"
                        "lang: pt-BR\n"
                        "authors: [uuid1, uuid2]\n"
                        "categories: [daily, categoria-adicional]\n"
                        "summary: 'Resumo em até 160 caracteres'\n"
                        "---\n\n"
                        "Seguido pelo corpo do fio."
                    ),
                },
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de UUIDs dos participantes deste fio específico",
                },
            },
            "required": ["title", "slug", "content", "participants"],
        },
    )


def sanitize_slug(slug: str, max_length: int = 50) -> str:
    """Sanitize and validate a slug to be URL-friendly.

    Args:
        slug: Raw slug from LLM
        max_length: Maximum length for the slug (default 50)

    Returns:
        Sanitized slug that is URL-friendly

    Examples:
        >>> sanitize_slug("A Pacificação Social")
        'a-pacificacao-social'
        >>> sanitize_slug("Frameworks vs Simplicidade!!!")
        'frameworks-vs-simplicidade'
        >>> sanitize_slug("Artigo_sobre_IA")
        'artigo-sobre-ia'
    """
    # Normalize unicode characters (remove accents)
    slug = unicodedata.normalize("NFKD", slug)
    slug = slug.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    slug = slug.lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove any character that isn't alphanumeric or hyphen
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Replace multiple consecutive hyphens with single hyphen
    slug = re.sub(r"-+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate to max_length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    # Fallback if slug is empty after sanitization
    if not slug:
        slug = "post"

    return slug


def get_available_tools():  # type: ignore[no-untyped-def]
    """Return all available function calling tools."""
    if types is None:
        raise RuntimeError(
            "A dependência opcional 'google-genai' não está instalada."
        )

    return [
        types.Tool(
            function_declarations=[
                get_write_post_declaration(),
            ]
        )
    ]
