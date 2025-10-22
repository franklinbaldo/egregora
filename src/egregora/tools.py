"""Function calling tools for LLM-driven post generation."""

from __future__ import annotations

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
            "required": ["title", "content", "participants"],
        },
    )


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
