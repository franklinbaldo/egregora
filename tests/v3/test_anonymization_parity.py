import hashlib
import pytest
from pathlib import Path

# Import the v3 anonymization functions
from egregora_v3.adapters.privacy.anonymize import anonymize_author, anonymize_mentions

@pytest.fixture
def raw_data_path() -> Path:
    """Returns the path to the raw data file for testing."""
    return Path("tests/v3/fixtures/raw_data.txt")

@pytest.fixture
def golden_text_path() -> Path:
    """Returns the path to the golden anonymized text file."""
    return Path("tests/v3/fixtures/golden_anonymization_data.txt")

@pytest.fixture
def golden_author_path() -> Path:
    """Returns the path to the golden anonymized author CSV file."""
    return Path("tests/v3/fixtures/golden_author_data.csv")

def test_anonymize_mentions_parity(raw_data_path, golden_text_path):
    """
    Tests that v3's anonymize_mentions produces byte-for-byte identical output to the golden file.
    """
    # Reconstruct the raw text with explicit unicode characters to ensure test consistency
    raw_text = (
        "This is a test message.\n"
        "Here's a mention to \u2068Jules\u2069.\n"
        "And another one to \u2068John Doe\u2069.\n"
        "This message is from Franklin.\n"
        "This one is from Jane Doe."
    )

    v3_output = anonymize_mentions(raw_text)
    golden_output = golden_text_path.read_text()

    assert v3_output.strip() == golden_output.strip()

def test_anonymize_author_parity(golden_author_path):
    """
    Tests that v3's anonymize_author produces byte-for-byte identical output to the golden file.
    """
    with open(golden_author_path, 'r') as f:
        for line in f:
            author, golden_anon_id = line.strip().split('|')
            v3_anon_id = anonymize_author(author)
            assert v3_anon_id == golden_anon_id

def test_anonymization_checksum():
    """
    Tests that the hash of the anonymization function's source code hasn't changed.
    This is a safeguard against accidental modifications to the privacy-critical code.
    """
    anonymization_v3_source = Path("src/egregora_v3/adapters/privacy/anonymize.py")
    if not anonymization_v3_source.exists():
        pytest.skip("Anonymization source file not found.")

    source_code = anonymization_v3_source.read_text()
    current_hash = hashlib.sha256(source_code.encode()).hexdigest()

    known_hash = "d701f8bf288666acb8b9ed68b6f1237912d0bc9251e9ad429a194a8eca8de755"

    assert current_hash == known_hash, "Anonymization source code has been modified!"
