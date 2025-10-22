from datetime import date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
from unittest.mock import MagicMock

import polars as pl
import pytest

_chromadb_module = ModuleType("chromadb")
_chromadb_utils = ModuleType("chromadb.utils")


class _DummyEmbeddingFunction:
    def __init__(self, *_, **__):
        pass

    def __call__(self, inputs):
        return [[0.0] for _ in inputs]


_chromadb_utils.embedding_functions = SimpleNamespace(
    GoogleGenerativeAiEmbeddingFunction=_DummyEmbeddingFunction
)
_chromadb_module.utils = _chromadb_utils
_chromadb_module.PersistentClient = SimpleNamespace

sys.modules.setdefault("chromadb", _chromadb_module)
sys.modules.setdefault("chromadb.utils", _chromadb_utils)

from egregora.config import (
    AnonymizationConfig,
    CacheConfig,
    EnrichmentConfig,
    PipelineConfig,
    ProfilesConfig,
)
from egregora.models import GroupSource, WhatsAppExport
from egregora.processor import UnifiedProcessor
from egregora.types import GroupSlug


@pytest.fixture()
def sample_dataframe() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "author": ["João Silva", "+55 21 99876-5432"],
            "message": ["Message 1", "Message 2"],
            "date": [date(2024, 1, 1), date(2024, 1, 1)],
            "timestamp": [
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 1, 13, 0),
            ],
        }
    )


def test_unified_processor_anonymizes_dataframe(monkeypatch, tmp_path, sample_dataframe):
    config = PipelineConfig(
        zip_files=[tmp_path / "dummy.zip"],
        posts_dir=tmp_path,
        enrichment=EnrichmentConfig(enabled=False),
        profiles=ProfilesConfig(enabled=False),
        anonymization=AnonymizationConfig(enabled=True, output_format="full"),
    )

    processor = UnifiedProcessor(config)

    sanitized_author = "Member-12345678-1234-1234-1234-123456789012"

    def fake_anonymize(df: pl.DataFrame, **_: object) -> pl.DataFrame:
        return df.with_columns(pl.lit(sanitized_author).alias("author"))

    monkeypatch.setattr("egregora.processor.Anonymizer.anonymize_dataframe", fake_anonymize)

    class StubExtractor:
        def __init__(self, *_, **__):
            pass

        @staticmethod
        def find_attachment_names_dataframe(_df):
            return set()

        def extract_specific_media_from_zip(self, *_args, **_kwargs):
            return {}

        @staticmethod
        def replace_media_references_dataframe(df, *_, **__):
            return df

        @staticmethod
        def build_public_paths(*_, **__):
            return {}

        @staticmethod
        def format_media_section(*_, **__):
            return ""

    monkeypatch.setattr("egregora.processor.MediaExtractor", StubExtractor)
    monkeypatch.setattr("egregora.processor.load_source_dataframe", lambda source: sample_dataframe)
    monkeypatch.setattr(
        "egregora.processor.validate_newsletter_privacy", lambda *_args, **_kwargs: None
    )

    generator = MagicMock()
    generator.generate.return_value = "Generated post"
    monkeypatch.setattr(
        "egregora.processor.PostGenerator", lambda config, gemini_manager: generator
    )

    source = GroupSource(
        slug=GroupSlug("test"),
        name="Test Group",
        exports=[
            WhatsAppExport(
                zip_path=tmp_path / "dummy.zip",
                group_name="Test Group",
                group_slug=GroupSlug("test"),
                export_date=date(2024, 1, 1),
                chat_file="chat.txt",
                media_files=[],
            )
        ],
    )

    post_paths = processor._process_source(source, days=None, from_date=None, to_date=None)

    assert post_paths, "Expected at least one generated post"

    args, kwargs = generator.generate.call_args
    context = args[1]
    assert sanitized_author in context.transcript


def test_media_enrichment_uses_first_matching_message(monkeypatch, tmp_path):
    media_key = "IMG(1).jpg"
    target_date = date(2024, 1, 1)
    messages = [
        f"Confira o arquivo {media_key} e novamente {media_key}.",
        f"Reenvio tardio de {media_key}.",
        None,
    ]
    sample_df = pl.DataFrame(
        {
            "author": ["Alice", "Bob", "Carol"],
            "message": messages,
            "date": [target_date] * 3,
            "timestamp": [
                datetime(2024, 1, 1, 8, 0),
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 1, 10, 0),
            ],
        }
    )

    zip_path = tmp_path / "dummy.zip"
    zip_path.write_bytes(b"")

    config = PipelineConfig(
        zip_files=[zip_path],
        posts_dir=tmp_path / "docs",
        enrichment=EnrichmentConfig(enabled=True),
        cache=CacheConfig(enabled=False),
        profiles=ProfilesConfig(enabled=False),
        anonymization=AnonymizationConfig(enabled=False),
        skip_existing_posts=False,
    )

    processor = UnifiedProcessor(config)

    monkeypatch.setattr(
        "egregora.processor.load_source_dataframe", lambda source: sample_df
    )

    captured_calls: list[dict[str, str]] = []
    saved_enrichments: list[dict[str, object]] = []

    class StubExtractor:
        def __init__(self, *_, **__):
            pass

        @staticmethod
        def find_attachment_names_dataframe(_df):
            return {media_key}

        def extract_specific_media_from_zip(self, *_args, **_kwargs):
            media_dir = config.posts_dir / "media"
            media_dir.mkdir(parents=True, exist_ok=True)
            media_file = SimpleNamespace(
                uuid="uuid-1234",
                dest_path=media_dir / "uuid-1234.jpg",
                media_type="image",
            )
            return {media_key: media_file}

        @staticmethod
        def replace_media_references_dataframe(df, *_, **__):
            return df

        @staticmethod
        def build_public_paths(*_, **__):
            return {}

        @staticmethod
        def format_media_section(*_, **__):
            return ""

    monkeypatch.setattr("egregora.processor.MediaExtractor", StubExtractor)

    async def fake_simple_enrich_media_with_cache(*_, context_message: str, **__):
        captured_calls.append({"context_message": context_message})
        return "media-summary"

    async def fake_simple_enrich_url_with_cache(*_args, **_kwargs):
        return "url-summary"

    def fake_save_media_enrichment(**payload):
        saved_enrichments.append(payload)

    monkeypatch.setattr(
        "egregora.processor.simple_enrich_media_with_cache",
        fake_simple_enrich_media_with_cache,
    )
    monkeypatch.setattr(
        "egregora.processor.simple_enrich_url_with_cache",
        fake_simple_enrich_url_with_cache,
    )
    monkeypatch.setattr("egregora.processor.save_media_enrichment", fake_save_media_enrichment)
    monkeypatch.setattr(
        "egregora.processor.save_simple_enrichment", lambda *_, **__: None
    )

    class StubGenerator:
        def __init__(self, *_args, **_kwargs):
            pass

        def generate(self, *_args, **_kwargs):
            return "Generated post"

    monkeypatch.setattr("egregora.processor.PostGenerator", StubGenerator)
    monkeypatch.setattr("egregora.processor.GeminiManager", lambda *_, **__: None)

    source = GroupSource(
        slug=GroupSlug("test"),
        name="Test Group",
        exports=[
            WhatsAppExport(
                zip_path=zip_path,
                group_name="Test Group",
                group_slug=GroupSlug("test"),
                export_date=target_date,
                chat_file="chat.txt",
                media_files=[],
            )
        ],
    )

    processor._process_source(source, days=None, from_date=None, to_date=None)

    assert captured_calls, "expected media enrichment to be invoked"
    assert saved_enrichments, "expected media enrichment to be saved"
    first_message = messages[0]
    assert captured_calls[0]["context_message"] == first_message
    assert saved_enrichments[0]["message"] == first_message


def test_url_enrichment_deduplicates_and_uses_cache(monkeypatch, tmp_path):
    target_date = date(2024, 1, 1)
    repeated_url = "http://alpha.test"
    unique_url = "https://beta.test"
    sample_df = pl.DataFrame(
        {
            "author": ["Alice", "Bob", "Carla", "Daniel"],
            "message": [
                f"Primeira menção {repeated_url}",
                f"Reforçando {repeated_url} novamente",
                f"Outro link {unique_url}",
                f"Mensagem tardia {repeated_url}",
            ],
            "date": [target_date] * 4,
            "timestamp": [
                datetime(2024, 1, 1, 8, 0),
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 1, 11, 0),
            ],
        }
    )

    sample_df = sample_df.with_columns(
        pl.col("timestamp")
        .dt.replace_time_zone("America/Porto_Velho")
        .dt.cast_time_unit("ns")
    )

    zip_path = tmp_path / "dummy.zip"
    zip_path.write_bytes(b"")

    config = PipelineConfig(
        zip_files=[zip_path],
        posts_dir=tmp_path / "docs",
        enrichment=EnrichmentConfig(enabled=True),
        cache=CacheConfig(
            enabled=True,
            cache_dir=Path("tests/tmp/cache"),
            auto_cleanup_days=None,
        ),
        profiles=ProfilesConfig(enabled=False),
        anonymization=AnonymizationConfig(enabled=False),
        skip_existing_posts=False,
    )

    processor = UnifiedProcessor(config)

    monkeypatch.setattr(
        "egregora.processor.load_source_dataframe", lambda source: sample_df
    )

    class StubExtractor:
        def __init__(self, *_, **__):
            pass

        @staticmethod
        def find_attachment_names_dataframe(_df):
            return set()

        def extract_specific_media_from_zip(self, *_args, **_kwargs):
            return {}

        @staticmethod
        def replace_media_references_dataframe(df, *_, **__):
            return df

        @staticmethod
        def build_public_paths(*_, **__):
            return {}

        @staticmethod
        def format_media_section(*_, **__):
            return ""

    monkeypatch.setattr("egregora.processor.MediaExtractor", StubExtractor)

    class FakeCache:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}
            self.get_calls: list[str] = []
            self.set_calls: list[tuple[str, str]] = []

        def get(self, key: str) -> str | None:
            self.get_calls.append(key)
            return self.store.get(key)

        def set(self, key: str, value: str) -> None:
            self.set_calls.append((key, value))
            self.store[key] = value

    fake_cache = FakeCache()

    monkeypatch.setattr("egregora.processor._create_cache", lambda *_: fake_cache)

    saved_enrichments: list[dict[str, object]] = []
    monkeypatch.setattr(
        "egregora.processor.save_simple_enrichment",
        lambda **payload: saved_enrichments.append(payload),
    )

    call_args: list[tuple[str, str]] = []

    async def fake_simple_enrich_url_with_cache(
        url: str, context_message: str, cache
    ) -> str:
        call_args.append((url, context_message))
        assert cache is fake_cache
        cached = cache.get(url)
        if cached is not None:
            return cached
        summary = f"summary:{url.split('//', 1)[-1]}"
        cache.set(url, summary)
        return summary

    monkeypatch.setattr(
        "egregora.processor.simple_enrich_url_with_cache",
        fake_simple_enrich_url_with_cache,
    )

    monkeypatch.setattr(
        "egregora.processor.PostGenerator",
        lambda *_args, **_kwargs: SimpleNamespace(generate=lambda *_, **__: "Generated"),
    )
    monkeypatch.setattr("egregora.processor.GeminiManager", lambda *_, **__: None)
    captured_frames: list[pl.DataFrame] = []

    monkeypatch.setattr(
        "egregora.processor.render_transcript",
        lambda df, *_, **__: (captured_frames.append(df), "Transcript")[1],
    )

    source = GroupSource(
        slug=GroupSlug("test"),
        name="Test Group",
        exports=[
            WhatsAppExport(
                zip_path=zip_path,
                group_name="Test Group",
                group_slug=GroupSlug("test"),
                export_date=target_date,
                chat_file="chat.txt",
                media_files=[],
            )
        ],
    )

    processor._process_source(source, days=None, from_date=None, to_date=None)

    assert call_args == [
        (repeated_url, sample_df.get_column("message")[0]),
        (unique_url, sample_df.get_column("message")[2]),
    ]
    assert [payload["url"] for payload in saved_enrichments] == [
        repeated_url,
        unique_url,
    ]
    assert fake_cache.get_calls == [repeated_url, unique_url]
    assert [key for key, _ in fake_cache.set_calls] == [repeated_url, unique_url]

    assert captured_frames, "expected transcript rendering to capture a dataframe"
    enriched_messages = captured_frames[0].filter(pl.col("author") == "egregora")
    assert enriched_messages.height == 2
    assert all(
        msg.startswith("📊 Análise de") and url in msg
        for msg, url in zip(
            enriched_messages.get_column("message").to_list(),
            [repeated_url, unique_url],
            strict=False,
        )
    )
