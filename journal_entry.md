## ⚡ 2026-01-21 - Removed Legacy RAG Method

**Observation:** While auditing the `src/egregora/rag/lancedb_backend.py` file, I found an `index_documents` method explicitly marked with a comment: "Alias for backward compatibility if needed, though we should use add()". This method was redundant as it merely called `self.add(docs)`.

**Action:**
- Verified that the `VectorStore` protocol only requires `add`, confirming `index_documents` was not part of the contract.
- Updated unit tests in `tests/unit/rag/test_lancedb_backend.py` and `tests/unit/rag/test_rag_comprehensive.py` to use `add` instead of the legacy alias.
- Removed the `index_documents` method from `LanceDBRAGBackend`.
- Cleaned up outdated comments in `tests/unit/rag/test_rag_interface.py` that incorrectly stated tests were failing due to missing methods.

**Reflection:** This removal simplifies the RAG backend interface, enforcing a single way to add documents (`add`). It eliminates confusion for future developers and aligns the implementation strictly with the `VectorStore` protocol. The existence of aliases often suggests a transition period that was never finalized; completing this transition is the essence of the Absolutist's work.
