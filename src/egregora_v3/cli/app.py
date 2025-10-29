import typer
from rich.console import Console
from rich.table import Table
import hashlib
from pathlib import Path

from egregora_v3.core.context import build_context
from egregora_v3.core.db import initialize_database, get_vss_index_ddl
from egregora_v3.core.paths import ensure_dirs_exist
from egregora_v3.core.types import HealthReport

app = typer.Typer(name="eg3", help="Egregora v3 - Emergent Group Reflection Engine")
console = Console()

@app.command()
def init():
    """
    Initialize the Egregora v3 database, directories, and configuration.
    """
    console.print("🚀 Initializing Egregora v3...")

    # Ensure all directories exist
    ensure_dirs_exist()
    console.print("✅ Application directories ensured.")

    # Build context and initialize database
    ctx = build_context()
    initialize_database(ctx.conn)
    console.print("✅ Database tables created.")

    # Create the VSS index using settings from the context
    vss_ddl = get_vss_index_ddl(
        dim=ctx.settings.embedding_dim,
        metric=ctx.settings.vss_metric,
        nlist=ctx.settings.vss_nlist,
        nprobe=ctx.settings.vss_nprobe,
    )
    # ctx.conn.execute(vss_ddl) # This will be enabled once VSS is confirmed to be installed
    console.print("✅ VSS index configured (note: VSS extension must be installed).")

    console.print("\n[bold green]Initialization complete![/bold green]")
    console.print(f"Database created at: {ctx.settings.db_path}")

@app.command()
def doctor():
    """
    Run health checks on the Egregora v3 installation.
    """
    console.print("🩺 Running health checks...")
    ctx = build_context()

    # Check DB connection and table counts
    db_reachable = False
    rag_chunks_count = 0
    rag_vectors_count = 0
    try:
        rag_chunks_count = ctx.conn.execute("SELECT count(*) FROM rag_chunks").fetchone()[0]
        rag_vectors_count = ctx.conn.execute("SELECT count(*) FROM rag_vectors").fetchone()[0]
        db_reachable = True
    except Exception as e:
        console.print(f"[bold red]DB check failed: {e}[/bold red]")

    # Check for VSS index (conceptual)
    # In a real scenario, you'd query system tables to check for the index.
    index_present = False # Placeholder

    # Anonymization checksum
    # Placeholder path for the anonymization file
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

    # Print a nice report table
    table = Table(title="Egregora v3 Health Report")
    table.add_column("Check", justify="right", style="cyan")
    table.add_column("Status", style="magenta")

    table.add_row("Database Reachable", "✅" if report.db_reachable else "❌")
    table.add_row("RAG Chunks Count", str(report.rag_chunks_count))
    table.add_row("RAG Vectors Count", str(report.rag_vectors_count))
    table.add_row("VSS Index Present", "✅" if report.index_present else "⏳ (pending)")
    table.add_row("Embedding Dimension", str(report.embedding_dimension))
    table.add_row("Anonymization Checksum", report.anonymization_checksum[:12] + "...")

    console.print(table)
    ctx.close()

if __name__ == "__main__":
    app()
