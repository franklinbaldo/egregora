"""Serialization helpers for pipeline stage artifacts.

Handles saving and loading Ibis Tables to/from CSV and Parquet formats for inter-stage communication.

Parquet is recommended for production use as it preserves schema and types, while CSV is
more human-readable and useful for debugging.
"""

import logging
from pathlib import Path
from typing import Annotated, Literal

import ibis
from ibis.expr.types import Table

logger = logging.getLogger(__name__)
SerializationFormat = Literal["csv", "parquet"]


def save_table_to_csv(
    table: Annotated[Table, "The Ibis table to save"],
    output_path: Annotated[Path, "The path to the output CSV file"],
    *,
    index: Annotated[bool, "Whether to include the row index in the output"] = False,
) -> None:
    """Save an Ibis Table to CSV file.

    Args:
        table: Ibis Table to save
        output_path: Path to output CSV file
        index: Whether to include row index (default: False)

    Raises:
        IOError: If writing fails

    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = table.execute()
    dataframe.to_csv(output_path, index=index)
    row_count = len(dataframe)
    logger.info("Saved %s rows to %s", row_count, output_path)


def load_table_from_csv(
    input_path: Annotated[Path, "The path to the input CSV file"],
    *,
    _schema: Annotated[dict | None, "An optional Ibis schema to apply to the loaded table"] = None,
) -> Table:
    """Load an Ibis Table from CSV file.

    Args:
        input_path: Path to input CSV file
        schema: Optional Ibis schema dict (currently unused, kept for API compatibility)

    Returns:
        Ibis Table loaded from CSV

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If CSV format is invalid

    """
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        msg = f"CSV file not found: {input_path}"
        raise FileNotFoundError(msg)
    table = ibis.read_csv(str(input_path))
    row_count = table.count().execute()
    logger.info("Loaded %s rows from %s", row_count, input_path)
    return table


def save_table_to_parquet(
    table: Annotated[Table, "The Ibis table to save"],
    output_path: Annotated[Path, "The path to the output Parquet file"],
) -> None:
    """Save an Ibis Table to Parquet file.

    Parquet preserves schema and types, making it more robust than CSV.
    Recommended for production pipelines.

    Args:
        table: Ibis Table to save
        output_path: Path to output Parquet file

    Raises:
        IOError: If writing fails

    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = table.execute()
    dataframe.to_parquet(output_path, engine="pyarrow", index=False)
    row_count = len(dataframe)
    logger.info("Saved %s rows to %s (Parquet)", row_count, output_path)


def load_table_from_parquet(input_path: Annotated[Path, "The path to the input Parquet file"]) -> Table:
    """Load an Ibis Table from Parquet file.

    Parquet preserves schema and types automatically.

    Args:
        input_path: Path to input Parquet file

    Returns:
        Ibis Table loaded from Parquet

    Raises:
        FileNotFoundError: If input file doesn't exist

    """
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        msg = f"Parquet file not found: {input_path}"
        raise FileNotFoundError(msg)
    table = ibis.read_parquet(str(input_path))
    row_count = table.count().execute()
    logger.info("Loaded %s rows from %s (Parquet)", row_count, input_path)
    return table
