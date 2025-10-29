import typer
from rich.console import Console
from rich.table import Table
import hashlib
from pathlib import Path

from egregora_v3.core.context import build_context
from egregora_v3.core.db import initialize_database, create_vss_index
from egregora_v3.core.paths import ensure_dirs_exist
from egregora_v3.core.types import HealthReport
from egregora_v3.features.rag.ingest import ingest_source
from egregora_v3.features.rag.build import build_embeddings
from egregora_v3.features.rag.query import query_rag
from egregora_v3.features.ranking.duel import run_duel
from egregora_v3.features.ranking.export import export_rankings
from egregora_v3.features.importer import import_from_parquet

app = typer.Typer(name="eg3", help="Egregora v3 - Emergent Group Reflection Engine")
rank_app = typer.Typer(name="rank", help="Commands for ranking content.")
site_app = typer.Typer(name="site", help="Commands for site generation.")
import_app = typer.Typer(name="import", help="Commands for importing data from v2.")
app.add_typer(rank_app)
app.add_typer(site_app)
app.add_typer(import_app)

console = Console()

@app.command()
def init():
    """
    Initialize the Egregora v3 database, directories, and configuration.
    """
    console.print("🚀 Initializing Egregora v3...")

    ensure_dirs_exist()
    console.print("✅ Application directories ensured.")

    ctx = build_context()
    initialize_database(ctx.conn, embedding_dim=ctx.settings.embedding_dim)
    create_vss_index(ctx.conn, metric=ctx.settings.vss_metric)
    console.print("✅ Database tables and VSS index created.")

    console.print("\n[bold green]Initialization complete![/bold green]")
    console.print(f"Database created at: {ctx.settings.db_path}")
    ctx.close()

@app.command()
def ingest(src: Path = typer.Argument(..., help="Path to a source file or directory to ingest.")):
    """
    Ingest and anonymize a source file or directory.
    """
    ctx = build_context()
    if src.is_dir():
        for f in src.glob("**/*"):
            if f.is_file():
                ingest_source(ctx, f)
    else:
        ingest_source(ctx, src)
    ctx.close()

@app.command()
def build():
    """
    Build the embeddings and vector store index.
    """
    ctx = build_context()
    build_embeddings(ctx)
    ctx.close()

@app.command()
def query(q: str = typer.Argument(..., help="The query string."),
          k: int = typer.Option(8, "--k", help="Number of results to return.")):
    """
    Query the RAG pipeline.
    """
    ctx = build_context()
    hits = query_rag(ctx, q, k)
    for hit in hits:
        console.print(f"[bold cyan]ID:[/] {hit.chunk.chunk_id[:12]}... [bold cyan]Similarity:[/] {hit.similarity:.4f}")
        console.print(hit.chunk.text)
        console.print("-" * 20)
    ctx.close()

@rank_app.command("duel")
def rank_duel(a: str = typer.Argument(..., help="Player A's ID."),
              b: str = typer.Argument(..., help="Player B's ID."),
              judge: str = typer.Option("gemini", "--judge", help="The judging strategy to use.")):
    """
    Run a duel between two players.
    """
    ctx = build_context()
    run_duel(ctx, a, b, judge)
    ctx.close()

@rank_app.command("export")
def rank_export(out: Path = typer.Argument(..., help="Output directory for the export."),
                fmt: str = typer.Option("parquet", "--fmt", help="Export format: 'parquet' or 'csv'.")):
    """
    Export the current rankings.
    """
    ctx = build_context()
    export_rankings(ctx, out, fmt)
    ctx.close()

@site_app.command("render")
def site_render():
    """
    Render the static site.
    """
    try:
        from egregora_v3.features.site.render import render_site  # type: ignore
    except ModuleNotFoundError as exc:
        console.print(
            "[bold red]Site rendering is unavailable:[/] "
            "missing 'egregora_v3.features.site.render'."
        )
        raise typer.Exit(code=1) from exc

    ctx = build_context()
    try:
        render_site(ctx)
    finally:
        ctx.close()

@import_app.command("parquet")
def import_parquet_cmd(in_path: Path = typer.Argument(..., help="Path to the v2 Parquet file.")):
    """
    Import chunks from a v2 Parquet file.
    """
    ctx = build_context()
    import_from_parquet(ctx, in_path)
    ctx.close()

def _status_icon(ok: bool) -> str:
    return "[bold green]✔[/bold green]" if ok else "[bold red]✘[/bold red]"


@app.command()
def doctor():
    """
    Run health checks on the Egregora v3 installation.
    """
    console.print("🩺 Running health checks...")
    ctx = build_context()

    db_reachable = False
    rag_chunks_count = 0
    rag_vectors_count = 0

    try:
        rag_chunks_count = ctx.conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
        rag_vectors_count = ctx.conn.execute("SELECT count(*) FROM rag_vectors").fetchone()[0]
        db_reachable = True
    except Exception as e:
        console.print(f"[bold red]DB check failed: {e}[/bold red]")

    index_present = False  # Placeholder

    anon_file_path = Path("src/egregora_v3/adapters/privacy/anonymize.py")
    anon_checksum = "file_not_found"
    if anon_file_path.exists():
        anon_checksum = hashlib.sha256(anon_file_path.read_bytes()).hexdigest()

    report = HealthReport(
        db_reachable=db_reachable,
        rag_chunks_count=rag_chunks_count,
        rag_vectors_count=rag_vectors_count,
        index_present=index_present,
        embedding_dimension=ctx.settings.embedding_dim,
        anonymization_checksum=anon_checksum
    )

    table = Table(title="Egregora v3 Health Report")
    table.add_column("Check", style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    table.add_row(
        "Database",
        _status_icon(report.db_reachable),
        f"{report.rag_chunks_count} chunks / {report.rag_vectors_count} vectors",
    )
    table.add_row(
        "Vector index",
        _status_icon(report.index_present),
        "Index not yet implemented" if not report.index_present else "Available",
    )
    table.add_row(
        "Embedding dim",
        "[bold green]✔[/bold green]",
        str(report.embedding_dimension),
    )
    table.add_row(
        "Anonymization checksum",
        "[bold green]✔[/bold green]" if anon_file_path.exists() else "[bold yellow]![/bold yellow]",
        report.anonymization_checksum,
    )

    console.print(table)
    ctx.close()

if __name__ == "__main__":
    app()
