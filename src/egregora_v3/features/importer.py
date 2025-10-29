import tempfile
from pathlib import Path

import duckdb
from rich.console import Console

from egregora_v3.core.context import Context
from egregora_v3.features.rag.build import build_embeddings
from egregora_v3.features.rag.ingest import ingest_source

console = Console()

def import_from_parquet(ctx: Context, parquet_path: Path):
    """
    Imports chunks from a v2 Parquet file, then re-embeds and builds the index.
    """
    if not parquet_path.exists():
        console.print(f"[bold red]Error:[/] Parquet file not found at {parquet_path}")
        return

    ctx.logger.info(f"Importing from Parquet file: {parquet_path}")

    try:
        rows = ctx.conn.execute(
            "SELECT text FROM read_parquet(?)",
            [str(parquet_path)],
        ).fetchall()
    except duckdb.Error as exc:
        console.print(f"[bold red]Error reading Parquet file:[/] {exc}")
        return

    if not rows:
        console.print(f"[yellow]No rows found in {parquet_path}.[/yellow]")
        return

    with tempfile.TemporaryDirectory(prefix="egregora_import_") as tmpdir:
        temp_dir = Path(tmpdir)
        for index, (text,) in enumerate(rows):
            if not isinstance(text, str):
                console.print(f"[yellow]Skipping row {index}: not a string.[/yellow]")
                continue
            temp_file = temp_dir / f"imported_{index}.md"
            temp_file.write_text(text)
            ingest_source(ctx, temp_file)

    console.print(f"Imported and ingested {len(rows)} chunks from {parquet_path}.")

    console.print("Building embeddings for imported chunks...")
    build_embeddings(ctx)
    console.print("Embedding build complete.")
