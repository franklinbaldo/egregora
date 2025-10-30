"""Serialization helpers for pipeline stage artifacts.

Handles saving and loading Ibis Tables to/from CSV format for inter-stage communication.
"""

import logging
from pathlib import Path

import ibis
from ibis.expr.types import Table

from ..core.schema import MESSAGE_SCHEMA, ensure_message_schema

logger = logging.getLogger(__name__)


def save_table_to_csv(table: Table, output_path: Path, *, index: bool = False) -> None:
    """
    Save an Ibis Table to CSV file.

    Args:
        table: Ibis Table to save
        output_path: Path to output CSV file
        index: Whether to include row index (default: False)

    Raises:
        IOError: If writing fails
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Execute table to pandas and save to CSV
    df = table.execute()
    df.to_csv(output_path, index=index)

    row_count = len(df)
    logger.info(f"Saved {row_count} rows to {output_path}")


def load_table_from_csv(input_path: Path, *, schema: dict | None = None) -> Table:
    """
    Load an Ibis Table from CSV file.

    Args:
        input_path: Path to input CSV file
        schema: Optional Ibis schema dict. If None, uses MESSAGE_SCHEMA.

    Returns:
        Ibis Table loaded from CSV

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If CSV format is invalid
    """
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"CSV file not found: {input_path}")

    if schema is None:
        schema = MESSAGE_SCHEMA

    # Read CSV with schema inference
    table = ibis.read_csv(str(input_path), table_schema=ibis.schema(schema))

    row_count = table.count().execute()
    logger.info(f"Loaded {row_count} rows from {input_path}")

    return table


def load_table_with_auto_schema(input_path: Path) -> Table:
    """
    Load an Ibis Table from CSV with automatic schema detection.

    Use this when the CSV might not match MESSAGE_SCHEMA (e.g., enriched tables).

    Args:
        input_path: Path to input CSV file

    Returns:
        Ibis Table loaded from CSV with auto-detected schema

    Raises:
        FileNotFoundError: If input file doesn't exist
    """
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"CSV file not found: {input_path}")

    # Let Ibis infer schema automatically
    table = ibis.read_csv(str(input_path))

    row_count = table.count().execute()
    logger.info(f"Loaded {row_count} rows from {input_path} (auto schema)")

    return table
