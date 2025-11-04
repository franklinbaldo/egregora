import pandas.testing as tm


def assert_parquet_equal(df1, df2, **kwargs):
    """Asserts that two DataFrames are equal."""
    tm.assert_frame_equal(df1, df2, check_dtype=False, **kwargs)
