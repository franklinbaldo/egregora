"""Helper script to rebuild the post index using LlamaIndex."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if TYPE_CHECKING:
    from egregora.rag.config import RAGConfig
    from egregora.rag.index import PostRAG


def _load_rag_components() -> tuple[type["RAGConfig"], type["PostRAG"]]:
    """Import the RAG configuration and index classes lazily.

    This keeps runtime imports out of the module level so Ruff does not flag
    them, while still allowing the script to be executed directly.
    """

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    config_module = import_module("egregora.rag.config")
    index_module = import_module("egregora.rag.index")
    return config_module.RAGConfig, index_module.PostRAG


def main() -> None:
    print("🚀 Migrando índice das posts para LlamaIndex...")

    rag_config_cls, post_rag_cls = _load_rag_components()

    posts_dir = PROJECT_ROOT / "data" / "posts"
    config = rag_config_cls(vector_store_type="chroma")

    rag = post_rag_cls(
        posts_dir=posts_dir,
        cache_dir=PROJECT_ROOT / "cache" / "rag",
        config=config,
    )

    print("📚 Recriando índice vetorial...")
    result = rag.update_index(force_rebuild=True)
    print(
        "✅ Concluído:",
        f"{result['posts_count']} posts",
        f"→ {result['chunks_count']} chunks",
    )

    print("\n🔍 Testando busca básica...")
    sample_results = rag.search("inteligência artificial", top_k=3)
    if not sample_results:
        print("Nenhum resultado encontrado. Verifique se existem posts indexadas.")
        return

    for index, node in enumerate(sample_results, start=1):
        metadata = getattr(node.node, "metadata", {})
        date_str = metadata.get("date", "desconhecida")
        preview = node.node.get_content()[:120].replace("\n", " ")
        print(f"{index}. {date_str} — score={node.score:.3f}: {preview}...")


if __name__ == "__main__":
    main()
