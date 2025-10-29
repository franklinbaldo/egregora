from typing import List

try:
    from google import genai  # type: ignore[import]
except ImportError:  # pragma: no cover - depends on optional dependency
    import google.generativeai as genai  # type: ignore[import]

class GeminiEmbeddingClient:
    """
    A client for generating embeddings using the Google Gemini API.
    """
    def __init__(self, api_key: str, model: str = "models/embedding-001"):
        self.model = model
        if api_key:
            genai.configure(api_key=api_key)

    def embed(self, texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
        """
        Generates embeddings for a list of texts.
        """
        if not texts:
            return []

        # The Gemini API can handle batching internally
        result = genai.embed_content(
            model=self.model,
            content=texts,
            task_type=task_type
        )
        return result['embedding']
