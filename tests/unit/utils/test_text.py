from src.egregora.utils.text import slugify


def test_slugify_simplified_lowercase():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_simplified_uppercase():
    assert slugify("Hello World!", lowercase=False) == "Hello-World"


def test_slugify_simplified_unicode():
    assert slugify("Café à Paris") == "café-à-paris"


def test_slugify_simplified_cyrillic():
    assert slugify("Привет мир") == "привет-мир"


def test_slugify_simplified_empty_string():
    assert slugify("") == ""


def test_slugify_simplified_none():
    assert slugify(None) == ""
