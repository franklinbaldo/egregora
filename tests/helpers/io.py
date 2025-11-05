import json

import pandas as pd


def read_parquet(path):
    """Reads a parquet file."""
    return pd.read_parquet(path)


def write_parquet(df, path):
    """Writes a DataFrame to a parquet file."""
    df.to_parquet(path, index=False)


def read_json(path):
    """Reads a json file."""
    with open(path) as f:
        return json.load(f)


def write_json(data, path):
    """Writes data to a json file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
