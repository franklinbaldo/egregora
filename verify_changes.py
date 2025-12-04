from egregora.data_primitives.document import Document, DocumentType

# Test 1: Semantic ID for Posts
post = Document(
    content="Test Post",
    type=DocumentType.POST,
    metadata={"slug": "semantic-test-post"}
)
print(f"Post ID (Expected: semantic-test-post): {post.document_id}")
assert post.document_id == "semantic-test-post"

# Test 2: Explicit ID Override
doc = Document(
    content="Test Doc",
    type=DocumentType.PROFILE,
    id="custom-id"
)
print(f"Explicit ID (Expected: custom-id): {doc.document_id}")
assert doc.document_id == "custom-id"

# Test 3: Fallback (No slug, no ID)
fallback = Document(
    content="Test Fallback",
    type=DocumentType.POST
)
print(f"Fallback ID (Expected: uuid-like): {fallback.document_id}")
assert len(fallback.document_id) > 20 # UUID length

# Test 4: ContentLibrary
from egregora_v3.core.catalog import ContentLibrary
import inspect
print(f"ContentLibrary exists and has typed fields: {inspect.get_annotations(ContentLibrary)}")

print("Verification Successful!")
