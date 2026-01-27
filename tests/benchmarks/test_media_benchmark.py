<<<<<<< HEAD
import ibis
<<<<<<< HEAD
<<<<<<< HEAD
import pandas as pd  # noqa: TID251
=======
import pandas as pd
>>>>>>> origin/pr/2706
=======
import pandas as pd
>>>>>>> origin/pr/2705
import pytest

from egregora.ops.media import extract_media_references


=======

import pytest
import pandas as pd
import ibis
from egregora.ops.media import extract_media_references

>>>>>>> origin/pr/2703
@pytest.fixture
def message_table():
    # Create a dummy table with messages containing media references
    data = {
        "text": [
            "Hello world",
            "Check this image: ![img](image1.jpg)",
            "Here is a file: file1.pdf (file attached)",
            "No media here",
            "Another image <attached: image2.png>",
            "Complex line with IMG-20210101-WA0001.jpg and other text",
            "Link to [doc](document.docx)",
<<<<<<< HEAD
        ]
        * 1000  # 7000 rows
=======
        ] * 1000  # 7000 rows
>>>>>>> origin/pr/2703
    }
    df = pd.DataFrame(data)
    con = ibis.duckdb.connect()
    return con.create_table("messages", df)

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2703
def test_extract_media_references_benchmark(benchmark, message_table):
    benchmark(extract_media_references, message_table)
