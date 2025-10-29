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

        embeddings: List[List[float]] = []
        for text in texts:
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type=task_type
            )

            embedding = getattr(result, "embedding", None)
            if embedding is None and isinstance(result, dict):
                embedding = result.get("embedding")

            if embedding is None:
                data = getattr(result, "data", None)
                if data:
                    try:
                        embedding = data[0].embedding
                    except (AttributeError, IndexError, KeyError, TypeError):
                        embedding = None

            if embedding is None:
                raise TypeError("Failed to extract embedding from Gemini response")

            values = None
            if hasattr(embedding, "values"):
                values = getattr(embedding, "values")
            elif isinstance(embedding, dict):
                values = embedding.get("values")
            elif isinstance(embedding, (list, tuple)):
                values = embedding

            if values is None:
                raise TypeError("Gemini embedding does not contain numeric values")

            try:
                numeric_values = [float(v) for v in values]
            except (TypeError, ValueError):
                raise TypeError("Gemini embedding values are not numeric") from None

            embeddings.append(numeric_values)

        return embeddings
