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
    df = table.execute()
    df.to_csv(output_path, index=index)
    row_count = len(df)
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


def load_table_with_auto_schema(input_path: Annotated[Path, "The path to the input CSV file"]) -> Table:
    """Load an Ibis Table from CSV with automatic schema detection.

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
        msg = f"CSV file not found: {input_path}"
        raise FileNotFoundError(msg)
    table = ibis.read_csv(str(input_path))
    row_count = table.count().execute()
    logger.info("Loaded %s rows from %s (auto schema)", row_count, input_path)
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
    df = table.execute()
    df.to_parquet(output_path, engine="pyarrow", index=False)
    row_count = len(df)
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


def save_table(
    table: Annotated[Table, "The Ibis table to save"],
    output_path: Annotated[Path, "The path to the output file, extension determines format if not specified"],
    *,
    file_format: Annotated[SerializationFormat, "The output format ('csv' or 'parquet')"] = "csv",
    index: Annotated[bool, "Whether to include the row index (only for CSV, ignored for Parquet)"] = False,
) -> None:
    """Save an Ibis Table to file with automatic format detection or explicit format.

    Args:
        table: Ibis Table to save
        output_path: Path to output file (extension determines format if format not specified)
        file_format: Output format ('csv' or 'parquet'). Auto-detected from extension if not provided.
        index: Whether to include row index (only for CSV, ignored for Parquet)

    Raises:
        ValueError: If format is unsupported
        IOError: If writing fails

    """
    output_path = Path(output_path)
    if output_path.suffix.lower() == ".parquet":
        save_table_to_parquet(table, output_path)
    elif output_path.suffix.lower() == ".csv":
        save_table_to_csv(table, output_path, index=index)
    elif file_format == "parquet":
        save_table_to_parquet(table, output_path)
    elif file_format == "csv":
        save_table_to_csv(table, output_path, index=index)
    else:
        msg = f"Unsupported format: {file_format}. Use 'csv' or 'parquet', or ensure file extension is .csv or .parquet"
        raise ValueError(msg)


def load_table(
    input_path: Annotated[Path, "The path to the input file"],
    *,
    file_format: Annotated[
        SerializationFormat | None,
        "The input format ('csv' or 'parquet'), auto-detected from extension if not provided",
    ] = None,
) -> Table:
    """Load an Ibis Table from file with automatic format detection.

    Args:
        input_path: Path to input file
        file_format: Input format ('csv' or 'parquet'). Auto-detected from extension if not provided.

    Returns:
        Ibis Table loaded from file

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If format cannot be determined or is unsupported

    """
    input_path = Path(input_path)
    if not input_path.exists():
        msg = f"File not found: {input_path}"
        raise FileNotFoundError(msg)
    detected_format = file_format
    if detected_format is None:
        if input_path.suffix.lower() == ".parquet":
            detected_format = "parquet"
        elif input_path.suffix.lower() == ".csv":
            detected_format = "csv"
        else:
            msg = f"Cannot detect format from extension '{input_path.suffix}'. Use .csv or .parquet, or specify format explicitly"
            raise ValueError(msg)
    if detected_format == "parquet":
        return load_table_from_parquet(input_path)
    if detected_format == "csv":
        return load_table_from_csv(input_path)
    msg = f"Unsupported format: {detected_format}"
    raise ValueError(msg)
