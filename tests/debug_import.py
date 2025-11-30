import ibis
from ibis import _

from egregora.input_adapters.whatsapp import filter_egregora_messages


def test_imports():
    assert ibis.__version__
    assert _ is not None
    assert filter_egregora_messages is not None
