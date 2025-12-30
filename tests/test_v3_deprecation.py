import pytest


def test_v3_is_deprecated():
    """
    Tests that the v3 version of the application is deprecated and cannot be imported.
    """
    with pytest.raises(ImportError):
        pass
