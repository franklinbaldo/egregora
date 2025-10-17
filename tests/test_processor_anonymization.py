from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from egregora.config import (
    AnonymizationConfig,
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

    monkeypatch.setattr("egregora.processor.MediaExtractor", StubExtractor)
    monkeypatch.setattr("egregora.processor.load_source_dataframe", lambda source: sample_dataframe)

    generator = MagicMock()
    generator.generate.return_value = "Generated post"
    monkeypatch.setattr("egregora.processor.PostGenerator", lambda config, gemini_manager: generator)

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
