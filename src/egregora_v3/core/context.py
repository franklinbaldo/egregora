from typing import Optional
import duckdb

from egregora_v3.core.config import Settings, load_settings
from egregora_v3.core.db import get_db_connection
from egregora_v3.core.logging import get_logger
from egregora_v3.adapters.embeddings.gemini import GeminiEmbeddingClient
from egregora_v3.adapters.vectorstore.duckdb_vss import DuckDBVectorStore

class Context:
    """
    The application context, holding all necessary components and state.
    """
    def __init__(self, settings: Settings, conn: duckdb.DuckDBPyConnection,
                 embedding_client: GeminiEmbeddingClient, vector_store: DuckDBVectorStore):
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

        # Initialize clients
        embedding_client = GeminiEmbeddingClient(
            api_key=settings.gemini_api_key,
            model=settings.embedding_model
        )
        vector_store = DuckDBVectorStore(conn, embedding_dim=settings.embedding_dim)

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
