"""Typer commands to control the FastMCP RAG server."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .server import FastMCPRAGServer

console = Console()
rag_app = typer.Typer(help="Ferramentas RAG baseadas em FastMCP e DuckDB.")


@rag_app.command("serve")
def serve_command(
    parquet: Path = typer.Argument(..., help="Arquivo Parquet com colunas vetoriais"),
    host: str = typer.Option("127.0.0.1", "--host", help="Endereço para escutar"),
    port: int = typer.Option(8765, "--port", help="Porta HTTP para o servidor FastMCP"),
    table_name: str = typer.Option("posts", "--table", help="Nome da tabela DuckDB"),
    vector_column: str = typer.Option("vector", "--vector-col", help="Coluna com embeddings"),
    text_column: str = typer.Option("message", "--text-col", help="Coluna usada para snippets"),
    top_k: int = typer.Option(3, "--top-k", min=1, help="Quantidade padrão de itens retornados"),
    min_similarity: float = typer.Option(
        0.0,
        "--min-similarity",
        help="Similaridade mínima (0 a 1) para filtrar resultados",
    ),
    install_vss: bool = typer.Option(
        True,
        "--install-vss/--no-install-vss",
        help="Tentar instalar e carregar a extensão DuckDB VSS",
    ),
    transport: str = typer.Option(
        "http",
        "--transport",
        help="Transporte FastMCP (http, sse ou streamable-http)",
    ),
) -> None:
    """Inicia o servidor FastMCP servindo consultas de similaridade."""

    try:
        server = FastMCPRAGServer(
            parquet_path=parquet,
            table_name=table_name,
            vector_column=vector_column,
            text_column=text_column,
            install_vss=install_vss,
            default_top_k=top_k,
            default_min_similarity=min_similarity,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"❌ {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="Servidor FastMCP RAG")
    table.add_column("Parâmetro")
    table.add_column("Valor")
    table.add_row("Parquet", str(parquet.resolve()))
    table.add_row("Tabela", server.index.table_name)
    table.add_row("Coluna vetorial", server.index.vector_column)
    table.add_row("Coluna texto", server.index.text_column or "(não disponível)")
    table.add_row("Top-K padrão", str(server.default_top_k))
    table.add_row("Similaridade mínima", f"{server.default_min_similarity:.3f}")
    table.add_row("VSS habilitado", "Sim" if server.index.vss_enabled else "Não (fallback Python)")
    table.add_row("Transporte", transport)
    table.add_row("Host", host)
    table.add_row("Porta", str(port))
    console.print(table)

    console.print("🚀 Iniciando servidor FastMCP. Pressione CTRL+C para encerrar.")
    try:
        server.run(host=host, port=port, transport=transport)
    except KeyboardInterrupt:  # pragma: no cover - CLI interaction
        console.print("👋 Servidor encerrado.")


@rag_app.command("dry-run")
def dry_run_command(
    parquet: Path = typer.Argument(..., help="Arquivo Parquet com colunas vetoriais"),
    query: str = typer.Argument(..., help="Consulta para testar similaridade"),
    top_k: int = typer.Option(3, "--top-k", min=1, help="Quantidade de resultados"),
    min_similarity: float = typer.Option(0.0, "--min-similarity", help="Similaridade mínima"),
    install_vss: bool = typer.Option(
        False,
        "--install-vss/--no-install-vss",
        help="Ativa tentativa de instalar a extensão VSS",
    ),
) -> None:
    """Executa uma consulta única sem subir o servidor FastMCP."""

    try:
        server = FastMCPRAGServer(
            parquet_path=parquet,
            install_vss=install_vss,
            default_top_k=top_k,
            default_min_similarity=min_similarity,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"❌ {exc}")
        raise typer.Exit(1) from exc

    frame = server.search(query, limit=top_k, min_similarity=min_similarity)
    if frame.is_empty():
        console.print("ℹ️ Nenhum resultado encontrado.")
        return

    console.print(frame)


__all__ = ["rag_app"]
