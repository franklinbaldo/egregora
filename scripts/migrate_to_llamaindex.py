"""Helper script to rebuild the post index using LlamaIndex."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from egregora.rag.config import RAGConfig  # noqa: E402
from egregora.rag.index import PostRAG  # noqa: E402


def main() -> None:
    print("🚀 Migrando índice das posts para LlamaIndex...")

    posts_dir = PROJECT_ROOT / "data" / "posts"
    config = RAGConfig(vector_store_type="chroma")

    rag = PostRAG(
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
