from pathlib import Path
import pandas as pd
from rich.console import Console

from egregora_v3.core.context import Context
from egregora_v3.features.rag.ingest import ingest_source
from egregora_v3.features.rag.build import build_embeddings

console = Console()

def import_from_parquet(ctx: Context, parquet_path: Path):
    """
    Imports chunks from a v2 Parquet file, then re-embeds and builds the index.
    """
    if not parquet_path.exists():
        console.print(f"[bold red]Error:[/] Parquet file not found at {parquet_path}")
        return

    ctx.logger.info(f"Importing from Parquet file: {parquet_path}")

    # Read the Parquet file into a Pandas DataFrame
    df = pd.read_parquet(parquet_path)

    # Assume the text is in a column named 'text' and is already anonymized
    if 'text' not in df.columns:
        console.print(f"[bold red]Error:[/] 'text' column not found in Parquet file.")
        return

    # Ingest each text as a separate document
    # TENET-BREAK(ingestion)[@franklin][P1][due:2025-12-15]:
    # tenet=clean; why=temporary use of file system for ingestion; exit=refactor to in-memory ingestion (#125)
    temp_dir = Path("/tmp/egregora_import")
    temp_dir.mkdir(exist_ok=True)

    for i, text in enumerate(df['text']):
        temp_file = temp_dir / f"imported_{i}.md"
        temp_file.write_text(text)
        ingest_source(ctx, temp_file)

    console.print(f"Imported and ingested {len(df)} chunks from {parquet_path}.")

    # After ingesting, run the build process to create embeddings
    console.print("Building embeddings for imported chunks...")
    build_embeddings(ctx)
    console.print("Embedding build complete.")
