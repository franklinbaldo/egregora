"""Integration tests covering keyword extraction and post retrieval."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig, RAGConfig
from egregora.rag.index import PostRAG
from egregora.rag.indexer import detect_post_date, hash_text
from egregora.rag.keyword_utils import KeywordExtractor, KeywordProvider
from egregora.rag.query_gen import QueryGenerator
from test_framework.helpers import (
    load_real_whatsapp_transcript,
    summarize_whatsapp_content,
)

BASELINE_PATH = Path(__file__).parent / "data" / "rag_query_baseline.json"
POSTS_FIXTURE = Path(__file__).parent / "data" / "rag_posts"


@pytest.fixture(scope="module")
def rag_baseline() -> dict[str, Any]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def rag_posts_dir(tmp_path: Path) -> Path:
    target = tmp_path / "posts"
    shutil.copytree(POSTS_FIXTURE, target)
    return target


@pytest.fixture()
def stub_keyword_provider() -> KeywordProvider:
    def _provider(text: str, *, max_keywords: int) -> list[str]:
        summary = summarize_whatsapp_content(text)
        keywords: list[str] = [author.lower() for author in summary["authors"]]
        if summary["has_media_attachment"]:
            keywords.append("anexos de mídia")
        keywords.append(str(summary["line_count"]))
        keywords.append("whatsapp")

        deduped: list[str] = []
        for keyword in keywords:
            if keyword not in deduped:
                deduped.append(keyword)
            if len(deduped) >= max_keywords:
                break
        return deduped[:max_keywords]

    return _provider


def test_keyword_extractor_uses_provider(
    whatsapp_real_content: str, stub_keyword_provider
) -> None:
    extractor = KeywordExtractor(
        max_keywords=5,
        keyword_provider=stub_keyword_provider,
    )
    keywords = extractor.extract(whatsapp_real_content)

    assert keywords
    assert len(keywords) <= 5
    assert keywords[0] == keywords[0].lower()


def test_query_generator_matches_baseline(
    whatsapp_real_content: str,
    rag_baseline: dict[str, object],
    stub_keyword_provider,
) -> None:
    generator = QueryGenerator(keyword_provider=stub_keyword_provider)
    result = generator.generate(whatsapp_real_content)

    expected = rag_baseline["query_generation"]["whatsapp_transcript"]
    assert result.keywords[: len(expected["keywords"])] == expected["keywords"]
    assert result.main_topics == expected["main_topics"]
    assert result.search_query == expected["search_query"]
    assert result.context.startswith("03/10/2025 09:45")


def test_query_generator_respects_max_keywords(
    whatsapp_real_content: str, stub_keyword_provider
) -> None:
    config = RAGConfig(max_keywords=3)
    generator = QueryGenerator(config, keyword_provider=stub_keyword_provider)
    result = generator.generate(whatsapp_real_content)

    assert len(result.keywords) <= 3


def test_post_rag_search_matches_baseline(
    rag_posts_dir: Path, rag_baseline: dict[str, object], tmp_path: Path
) -> None:
    config = RAGConfig(
        persist_dir=tmp_path / "vector",
        cache_dir=tmp_path / "cache",
        min_similarity=0.0,
        top_k=3,
    )
    rag = PostRAG(posts_dir=rag_posts_dir, config=config)
    rag.update_index(force_rebuild=True)

    expected_queries = rag_baseline["post_search_queries"]
    expected_results = rag_baseline["post_search"]

    for slug, query in expected_queries.items():
        hits = rag.search(query, top_k=3, min_similarity=0.0)
        assert hits, f"expected hits for query '{query}'"

        expected_hit = expected_results[slug]
        observed_files = []
        for hit in hits:
            metadata = getattr(hit.node, "metadata", {}) or {}
            observed_files.append(metadata.get("file_name"))
        expected_files = [item["file"] for item in expected_hit]
        assert observed_files == expected_files

        for hit, expected_info in zip(hits, expected_hit, strict=True):
            assert hit.node.ref_doc_id == expected_info["doc_id"]
            assert hit.score == pytest.approx(expected_info["score"], rel=0.05, abs=0.01)


def test_post_date_detection() -> None:
    test_files = [
        "2025-10-03.md",
        "post-2025-10-03.md",
        "daily-2025-12-25.txt",
        "no-date-file.md",
    ]
    expected_dates = [
        date(2025, 10, 3),
        date(2025, 10, 3),
        date(2025, 12, 25),
        None,
    ]

    for filename, expected in zip(test_files, expected_dates, strict=True):
        result = detect_post_date(Path(filename))
        assert result == expected, f"Failed for {filename}: got {result}, expected {expected}"


def test_rag_config_validation(temp_dir: Path) -> None:
    configs = [
        RAGConfig(enabled=True, max_context_chars=1000),
        RAGConfig(enabled=False),
        RAGConfig(enabled=True, min_similarity=0.8),
    ]

    for rag_config in configs:
        config = PipelineConfig.with_defaults(
            zips_dir=temp_dir,
            posts_dir=temp_dir,
        )
        config.rag = rag_config

        assert config.rag.enabled == rag_config.enabled
        if rag_config.enabled:
            assert config.rag.max_context_chars > 0
            assert 0.0 <= config.rag.min_similarity <= 1.0


def test_whatsapp_data_processing_pipeline(temp_dir: Path, whatsapp_zip_path: Path) -> None:
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()

    test_zip = zips_dir / "2025-10-03.zip"
    shutil.copy2(whatsapp_zip_path, test_zip)

    assert test_zip.exists()

    content = load_real_whatsapp_transcript(test_zip)
    metadata = summarize_whatsapp_content(content)
    assert metadata["url_count"] >= 1
    assert metadata["has_media_attachment"]
    assert metadata["authors"]


def test_text_hashing_functionality(whatsapp_real_content: str) -> None:
    lines = [
        line for line in whatsapp_real_content.splitlines()
        if line.startswith("03/10/2025") and "Franklin:" in line
    ]
    assert len(lines) >= 3

    whatsapp_texts = [lines[0], lines[1], lines[0]]

    hashes = [hash_text(text) for text in whatsapp_texts]

    assert len(hashes) == 3
    assert all(isinstance(h, str) for h in hashes)
    assert all(len(h) > 0 for h in hashes)
    assert hashes[0] == hashes[2]
    assert hashes[0] != hashes[1]
