
import ibis
import pandas as pd
from datetime import datetime
from egregora.data_primitives.document import Document, DocumentType
from egregora.agents.enricher import _extract_media_candidates

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
print("Running extraction...")
candidates = _extract_media_candidates(messages_table, media_mapping, limit=50)
print(f"Candidates found: {len(candidates)}")
for ref, doc, meta in candidates:
    print(f"Ref: {ref}")
    print(f"Doc filename: {doc.metadata.get('filename')}")
