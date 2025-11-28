
from datetime import datetime

import ibis
import pandas as pd

from egregora.agents.enricher import _extract_media_candidates
from egregora.data_primitives.document import Document, DocumentType

# Mock messages table
data = {
    "ts": [datetime.now()],
    "text": ["[Video](VID-20250302-WA0034.mp4)"],
    "event_id": ["evt1"],
    "tenant_id": ["tenant1"],
    "source": ["whatsapp"],
    "thread_id": ["thread1"],
    "author_uuid": ["auth1"],
    "created_at": [datetime.now()],
    "created_by_run": ["run1"]
}
messages_table = ibis.memtable(pd.DataFrame(data))

# Mock media mapping
media_ref = "VID-20250302-WA0034.mp4"
media_doc = Document(
    content=b"fake video content",
    type=DocumentType.MEDIA,
    metadata={
        "original_filename": media_ref,
        "filename": "vid-20250302-wa0034.mp4",
        "media_type": "video"
    }
)
media_mapping = {media_ref: media_doc}

# Run extraction
candidates = _extract_media_candidates(messages_table, media_mapping, limit=50)
for _ref, _doc, _meta in candidates:
    pass
