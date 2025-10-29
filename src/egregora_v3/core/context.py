from typing import Optional
import duckdb

from egregora_v3.core.config import Settings, load_settings
from egregora_v3.core.db import get_db_connection, initialize_database
from egregora_v3.core.logging import get_logger

# Placeholder for actual client implementations
class EmbeddingClient:
    pass

class VectorStore:
    pass

class Context:
    """
    The application context, holding all necessary components and state.
    """
    def __init__(self, settings: Settings, conn: duckdb.DuckDBPyConnection,
                 embedding_client: EmbeddingClient, vector_store: VectorStore):
        self.settings = settings
        self.conn = conn
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.logger = get_logger(__name__)

    @classmethod
    def from_settings(cls, settings: Settings):
        """
        Creates a new Context instance from a Settings object.
        """
        # Set up database connection
        conn = get_db_connection(settings.db_path)

        # Initialize clients (placeholders for now)
        # In a real implementation, you'd instantiate these from adapters
        # e.g., embedding_client = GeminiEmbeddingClient(api_key=settings.gemini_api_key)
        embedding_client = EmbeddingClient()
        vector_store = VectorStore()

        return cls(settings, conn, embedding_client, vector_store)

    def close(self):
        """Closes the database connection."""
        self.conn.close()

def build_context(cli_overrides: Optional[dict] = None):
    """
    A factory function to build the full application context.
    """
    settings = load_settings(cli_overrides)
    return Context.from_settings(settings)
