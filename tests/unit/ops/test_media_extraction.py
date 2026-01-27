import ibis
<<<<<<< HEAD
import pandas as pd  # noqa: TID251
=======
import pandas as pd
<<<<<<< HEAD
>>>>>>> origin/pr/2706
=======
>>>>>>> origin/pr/2705
import pytest

from egregora.ops.media import extract_media_references


@pytest.fixture
def mock_table():
    data = {
        "text": [
            "Normal text",
            "Image ![alt](img1.jpg)",
            "Link [doc](doc.pdf)",
            "Raw file.pdf (file attached)",
            "WhatsApp IMG-20210101-WA0001.jpg",
            None,
            "",
            "Multiple: ![a](1.jpg) and ![b](2.png)",
            "External [link](https://google.com) should be ignored",
            "Internal [link](/local/path) should be captured",
        ]
    }
    # Create an in-memory DuckDB table
    con = ibis.duckdb.connect()
    return con.create_table("messages", pd.DataFrame(data))


def test_extract_media_references_logic(mock_table):
    refs = extract_media_references(mock_table)

    expected = {
        "img1.jpg",
        "doc.pdf",
        "file.pdf",
        "IMG-20210101-WA0001.jpg",
        "1.jpg",
        "2.png",
        "/local/path",  # This is captured by design (relative link)
    }

    assert refs == expected


def test_extract_media_references_empty():
    con = ibis.duckdb.connect()
    # Create empty table with explicit schema
    t = con.create_table("empty", schema=ibis.schema({"text": "string"}))
    assert extract_media_references(t) == set()
