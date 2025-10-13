
import polars as pl
from egregora.ingest.anonymizer import Anonymizer

def test_anonymize_dataframe_adds_anon_author_column():
    df = pl.DataFrame({
        "author": ["John Doe", "Jane Doe"],
        "message": ["Hello", "Hi"],
    })
    anonymized_df = Anonymizer.anonymize_dataframe(df)
    assert "anon_author" in anonymized_df.columns
    assert anonymized_df["anon_author"][0].startswith("Member-")
    assert anonymized_df["anon_author"][1].startswith("Member-")
