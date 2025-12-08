from egregora.utils.filesystem import _extract_clean_date


def test_extract_clean_date_valid():
    assert _extract_clean_date("2023-01-01") == "2023-01-01"
    assert _extract_clean_date("  2023-01-01  ") == "2023-01-01" # strip() makes this valid for match

def test_extract_clean_date_starts_with():
    # re.match only matches start of string
    assert _extract_clean_date("2023-01-01-slug") == "2023-01-01"
    assert _extract_clean_date("2023-01-01 some text") == "2023-01-01"

def test_extract_clean_date_no_match():
    # These return original string if no match found at start
    assert _extract_clean_date("prefix 2023-01-01 suffix") == "prefix 2023-01-01 suffix"
    assert _extract_clean_date("not a date") == "not a date"
    assert _extract_clean_date("2023-13-01") == "2023-13-01"  # Invalid month
    assert _extract_clean_date("") == ""
