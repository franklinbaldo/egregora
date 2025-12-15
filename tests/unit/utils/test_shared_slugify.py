import pytest
from egregora.utils.paths import slugify as v2_slugify
from egregora_v3.core.utils import slugify as v3_slugify

@pytest.mark.parametrize("input_text,expected_slug", [
    ("Hello World", "hello-world"),
    ("Café à Paris", "cafe-a-paris"),
    ("  Spaced  Out  ", "spaced-out"),
    ("Multi--Dash", "multi-dash"),
    ("No Special: @#$%", "no-special"),
    ("Snake_Case", "snake-case"),
])
def test_slugify_consistency(input_text, expected_slug):
    """Ensure both V2 and V3 slugify produce identical, clean slugs."""
    v2_result = v2_slugify(input_text)
    v3_result = v3_slugify(input_text)

    assert v2_result == expected_slug
    assert v3_result == expected_slug
    assert v2_result == v3_result

def test_slugify_defaults():
    """Ensure V2 maintains legacy 'post' default while V3 uses 'untitled'."""
    assert v2_slugify("") == "post"
    assert v3_slugify("") == "untitled"

def test_slugify_lowercase_option():
    """Ensure both support case preservation if requested."""
    input_text = "Hello World"
    expected_mixed = "Hello-World"

    assert v2_slugify(input_text, lowercase=False) == expected_mixed
    assert v3_slugify(input_text, lowercase=False) == expected_mixed
