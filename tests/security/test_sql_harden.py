import pytest
from unittest.mock import MagicMock
from egregora.agents.shared.annotations import AnnotationStore, ANNOTATIONS_TABLE
from egregora.database.utils import quote_identifier

def test_annotations_table_constant_is_safe():
    """Verify the table constant is just a string and quote_identifier works."""
    assert ANNOTATIONS_TABLE == "annotations"
    quoted = quote_identifier(ANNOTATIONS_TABLE)
    assert quoted == '"annotations"'

def test_quote_identifier_logic():
    """Verify quote_identifier escapes quotes."""
    assert quote_identifier('simple') == '"simple"'
    assert quote_identifier('with"quote') == '"with""quote"'
    assert quote_identifier('drop table "users"') == '"drop table ""users"""'
