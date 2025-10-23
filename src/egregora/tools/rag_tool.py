from pathlib import Path
from .registry import Tool
from ..rag.chromadb_rag import ChromadbRAG


class RAGTool(Tool):
    def __init__(self, persist_dir: Path):
        self.rag = ChromadbRAG(persist_dir=persist_dir)

    async def execute(self, query: str, top_k: int = 5) -> list[dict]:
        results = self.rag.search(query, top_k=top_k)
        return [
            {
                "content": r.get("content", ""),
                "metadata": r.get("metadata", {}),
                "score": r.get("score", 0.0),
            }
            for r in results
        ]
