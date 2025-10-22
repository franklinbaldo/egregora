from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import polars as pl
import pytest

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
