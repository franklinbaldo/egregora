"""Utilities for creating deterministic fingerprints of data."""
import hashlib
from typing import Any
import ibis

def fingerprint_table(table: ibis.Table) -> str:
    """Generate a deterministic SHA256 fingerprint of an Ibis table."""
    # Ensure a deterministic order for hashing.
    # Sorting by all columns is a reliable way to do this if no primary key is known.
    sorted_table = table.order_by(*table.columns)

    sample = sorted_table.limit(1000).execute()
    data_str = sample.to_csv(index=False)

    schema_str = str(table.schema())
    combined = f"{schema_str}\n{data_str}"

    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return f"sha256:{hash_obj.hexdigest()}"

def fingerprint_window(window: Any) -> str:
    """Generate SHA256 fingerprint of a window slice."""
    metadata_str = (
        f"{window.window_index}|{window.start_time.isoformat()}|{window.end_time.isoformat()}|{window.size}"
    )
    hash_obj = hashlib.sha256(metadata_str.encode("utf-8"))
    return f"sha256:{hash_obj.hexdigest()}"
