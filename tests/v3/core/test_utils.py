from src.egregora_v3.core.utils import slugify

def test_slugify_lowercase():
    assert slugify("Hello World!") == "hello-world"

def test_slugify_uppercase():
    assert slugify("Hello World!", lowercase=False) == "Hello-World"

def test_slugify_unicode():
    assert slugify("Café à Paris") == "cafe-a-paris"

def test_slugify_cyrillic():
    assert slugify("Привет мир") == "post"

def test_slugify_path_traversal():
    assert slugify("../../etc/passwd") == "etcpasswd"

def test_slugify_max_len():
    assert slugify("A" * 100, max_len=20) == "aaaaaaaaaaaaaaaaaaaa"

def test_slugify_empty_string():
    assert slugify("") == "post"

def test_slugify_none():
    assert slugify(None) == ""

def test_slugify_trailing_hyphen():
    assert slugify("a-b-c-" * 20, max_len=20) == "a-b-c-a-b-c-a-b-c-a"
