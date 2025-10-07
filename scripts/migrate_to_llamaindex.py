"""Helper script to rebuild the newsletter index using LlamaIndex."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from egregora.rag.config import RAGConfig
from egregora.rag.index import NewsletterRAG


def main() -> None:
    print("🚀 Migrando índice das newsletters para LlamaIndex...")

    newsletters_dir = PROJECT_ROOT / "data" / "newsletters"
    config = RAGConfig(vector_store_type="chroma")

    rag = NewsletterRAG(
        newsletters_dir=newsletters_dir,
        cache_dir=PROJECT_ROOT / "cache" / "rag",
        config=config,
    )

    print("📚 Recriando índice vetorial...")
    result = rag.update_index(force_rebuild=True)
    print(
        "✅ Concluído:",
        f"{result['newsletters_count']} newsletters",
        f"→ {result['chunks_count']} chunks",
    )

    print("\n🔍 Testando busca básica...")
    sample_results = rag.search("inteligência artificial", top_k=3)
    if not sample_results:
        print("Nenhum resultado encontrado. Verifique se existem newsletters indexadas.")
        return

    for index, node in enumerate(sample_results, start=1):
        metadata = getattr(node.node, "metadata", {})
        date_str = metadata.get("date", "desconhecida")
        preview = node.node.get_content()[:120].replace("\n", " ")
        print(f"{index}. {date_str} — score={node.score:.3f}: {preview}...")


if __name__ == "__main__":
    main()
