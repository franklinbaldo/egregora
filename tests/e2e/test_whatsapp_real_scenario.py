from __future__ import annotations

import string
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import ibis
import pytest

from egregora.config.settings import create_default_config
from egregora.enrichment.media import extract_and_replace_media
from egregora.enrichment.runners import EnrichmentRuntimeContext, enrich_table
from egregora.input_adapters.whatsapp.parser import filter_egregora_messages, parse_source
from egregora.orchestration.write_pipeline import process_whatsapp_export
from egregora.utils.cache import EnrichmentCache
from egregora.utils.zip import ZipValidationError, validate_zip_contents

if TYPE_CHECKING:
    from conftest import WhatsAppFixture


def create_export_from_fixture(fixture: WhatsAppFixture):
    return fixture.create_export()


def _bootstrap_site(tmp_path: Path) -> Path:
    """Bootstrap a test site with MODERN structure (content at root level)."""
    site_root = tmp_path / "site"
    posts_dir = site_root / "posts"
    profiles_dir = site_root / "profiles"
    media_dir = site_root / "media"

    posts_dir.mkdir(parents=True)
    profiles_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)

    # MODERN: mkdocs.yml in .egregora/ with docs_dir: ..
    egregora_dir = site_root / ".egregora"
    egregora_dir.mkdir(parents=True)
    mkdocs_path = egregora_dir / "mkdocs.yml"
    mkdocs_path.write_text("site_name: Test Suite\ndocs_dir: ..\n", encoding="utf-8")
    return site_root


class DummyGenaiClient:
    """Dummy Google GenAI client for testing.

    Supports:
    - Pydantic-AI agent calls (models.generate_content)
    - File uploads (files.upload)
    - Embeddings (models.embed_content)
    """

    def __init__(self, *args, **kwargs):
        # Response for pydantic-ai agents - needs text attribute
        def dummy_generate(*a, **k):
            return SimpleNamespace(
                text='{"markdown": "Test enrichment content"}',
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(
                            parts=[SimpleNamespace(text='{"markdown": "Test enrichment content"}')]
                        )
                    )
                ],
            )

        # Embedding response
        def dummy_embed(*a, **k):
            return SimpleNamespace(embedding=SimpleNamespace(values=[0.1] * 768))

        self.models = SimpleNamespace(
            generate_content=dummy_generate,
            embed_content=dummy_embed,
        )
        self.aio = SimpleNamespace(models=self.models)

        # File upload support
        def dummy_upload(*a, **k):
            return SimpleNamespace(
                uri="stub://file",
                mime_type="image/jpeg",
                name="stub-file",
                state=SimpleNamespace(name="ACTIVE"),
            )

        self.files = SimpleNamespace(
            upload=dummy_upload,
            get=lambda name: SimpleNamespace(
                uri="stub://file", mime_type="image/jpeg", name=name, state=SimpleNamespace(name="ACTIVE")
            ),
        )

    def close(self):  # pragma: no cover - compatibility shim
        return None


def _install_pipeline_stubs(monkeypatch, captured_dates: list[str]):
    monkeypatch.setattr("egregora.orchestration.write_pipeline.genai.Client", DummyGenaiClient)
    # Note: GeminiDispatcher has been removed - pipeline now uses genai.Client directly

    def _stub_writer(
        table,
        start_time,
        end_time,
        client,
        config=None,
    ):
        """Stub writer matching new signature: write_posts_for_window(table, start_time, end_time, client, config)."""
        window_label = f"{start_time:%Y-%m-%d %H:%M} to {end_time:%H:%M}"
        captured_dates.append(window_label)

        # Extract paths from config if provided, otherwise use dummy paths
        if config:
            output_dir = config.output_dir
            profiles_dir = config.profiles_dir
        else:
            # Fallback for tests without config
            output_dir = Path("dummy_output")
            profiles_dir = Path("dummy_profiles")

        output_dir.mkdir(parents=True, exist_ok=True)
        profiles_dir.mkdir(parents=True, exist_ok=True)

        post_filename = f"{start_time:%Y%m%d_%H%M%S}-stub.md"
        post_path = output_dir / post_filename
        post_path.write_text(
            "---\n"
            f"title: Stub Post for {window_label}\n"
            f"date: {start_time:%Y-%m-%d}\n"
            "tags: []\n"
            "---\n"
            "This is a placeholder post used during testing.\n",
            encoding="utf-8",
        )

        profile_path = profiles_dir / "stub-profile.md"
        profile_path.write_text("stub profile", encoding="utf-8")

        return {"posts": [str(post_path)], "profiles": [str(profile_path)]}

    monkeypatch.setattr("egregora.pipeline.runner.write_posts_for_window", _stub_writer)


def test_zip_extraction_completes_without_error(whatsapp_fixture: WhatsAppFixture):
    zip_path = whatsapp_fixture.zip_path
    with zipfile.ZipFile(zip_path) as archive:
        validate_zip_contents(archive)
        members = archive.namelist()

    assert "Conversa do WhatsApp com Teste.txt" in members
    assert sum(1 for member in members if member.endswith(".jpg")) == 4


def test_parser_produces_valid_table(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    assert {"timestamp", "author", "message"}.issubset(table.columns)
    assert table.count().execute() == 10
    messages = table["message"].execute().tolist()
    assert all(message is not None and message.strip() for message in messages)

    timestamps = table["timestamp"].execute()
    assert all(ts.tzinfo is not None for ts in timestamps)


def test_parser_handles_portuguese_dates(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)
    dates = [value.date() for value in table["date"].execute().tolist()]

    assert date(2025, 10, 28) in dates


def test_parser_preserves_all_messages(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    participant_rows = table.filter(~table.author.isin(["system", "egregora"]))
    assert participant_rows.count().execute() == 10


def test_parser_extracts_media_references(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    combined = " ".join(table["message"].execute().tolist())
    assert "IMG-20251028-WA0035.jpg" in combined
    assert "arquivo anexado" in combined


def test_anonymization_removes_real_author_names(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    authors = table["author"].execute().tolist()
    for forbidden in ("Franklin", "Iuri Brasil", "Você", "Eurico Max"):
        assert forbidden not in authors

    messages = table["message"].execute().tolist()
    assert any("@" in message and "teste de menção" in message for message in messages)


def test_parse_source_exposes_raw_authors_when_requested(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(
        export,
        timezone=whatsapp_fixture.timezone,
        expose_raw_author=True,
    )

    authors = table.select("author").distinct().execute()["author"].tolist()
    for expected in ("Franklin", "Iuri Brasil", "Você", "Eurico Max"):
        assert expected in authors


def test_anonymization_is_deterministic(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table_one = parse_source(export, timezone=whatsapp_fixture.timezone)
    table_two = parse_source(export, timezone=whatsapp_fixture.timezone)

    authors_one = sorted(table_one.select("author").distinct().execute()["author"].tolist())
    authors_two = sorted(table_two.select("author").distinct().execute()["author"].tolist())

    assert authors_one == authors_two


def test_anonymized_uuids_are_valid_format(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    distinct_authors = table.select("author").distinct().execute()["author"].tolist()
    authors = [value for value in distinct_authors if value not in {"system", "egregora"}]
    valid_chars = set(string.hexdigits.lower())
    for author_id in authors:
        assert len(author_id) == 8
        assert set(author_id) <= valid_chars


def test_media_extraction_creates_expected_files(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    _, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    assert len(media_mapping) == 4
    for extracted_path in media_mapping.values():
        assert extracted_path.exists()


def test_media_references_replaced_in_messages(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, _ = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    joined_messages = " ".join(updated_table["message"].execute().dropna().tolist())
    assert "![Image]" in joined_messages


def test_media_files_have_deterministic_names(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir_one = tmp_path / "docs1"
    docs_dir_two = tmp_path / "docs2"
    posts_one = docs_dir_one / "posts"
    posts_two = docs_dir_two / "posts"
    docs_dir_one.mkdir()
    docs_dir_two.mkdir()
    posts_one.mkdir()
    posts_two.mkdir()

    _, mapping_one = extract_and_replace_media(table, export.zip_path, docs_dir_one, posts_one)
    _, mapping_two = extract_and_replace_media(table, export.zip_path, docs_dir_two, posts_two)

    assert mapping_one.keys() == mapping_two.keys()
    for key in mapping_one:
        assert mapping_one[key].name == mapping_two[key].name


def test_full_pipeline_completes_without_crash(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    site_root = _bootstrap_site(tmp_path)
    processed_dates: list[str] = []
    _install_pipeline_stubs(monkeypatch, processed_dates)

    results = process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    assert results
    assert processed_dates == ["2025-10-28 14:10 to 14:15"]


def test_pipeline_creates_expected_directory_structure(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    site_root = _bootstrap_site(tmp_path)
    _install_pipeline_stubs(monkeypatch, [])

    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    # MODERN: content at root level, not in docs/
    assert (site_root / "posts").exists()
    assert (site_root / "profiles").exists()
    assert (site_root / "media").exists()
    assert (site_root / ".egregora").exists()


def test_pipeline_respects_date_range_filters(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    site_root = _bootstrap_site(tmp_path)
    processed_dates: list[str] = []
    _install_pipeline_stubs(monkeypatch, processed_dates)

    results = process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        from_date=date(2025, 10, 29),
        to_date=date(2025, 10, 29),
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    assert results == {}
    assert processed_dates == []


def test_egregora_commands_are_filtered_out(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    original_records = table.execute().to_dict("records")
    sample_record = original_records[0]
    synthetic = {
        **sample_record,
        "message": "/egregora opt-out",
    }
    augmented = table.union(ibis.memtable([synthetic], schema=table.schema()))

    filtered, removed_count = filter_egregora_messages(augmented)
    assert removed_count == 1

    messages = " ".join(filtered["message"].execute().dropna().tolist())
    assert "/egregora opt-out" not in messages


def test_enrichment_adds_egregora_messages(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    cache = EnrichmentCache(tmp_path / "cache")

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_url": False}),
        },
    )

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
    )

    try:
        enriched = enrich_table(
            updated_table,
            media_mapping,
            config=config,
            context=enrichment_context,
        )
    finally:
        cache.close()

    assert enriched.count().execute() >= updated_table.count().execute()
    assert enriched.filter(enriched.author == "egregora").count().execute() > 0


def test_pipeline_handles_missing_media_gracefully(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
    monkeypatch,
    gemini_api_key: str,
):
    corrupted_zip = tmp_path / "corrupted.zip"
    with (
        zipfile.ZipFile(whatsapp_fixture.zip_path) as source,
        zipfile.ZipFile(corrupted_zip, "w") as target,
    ):
        for info in source.infolist():
            if info.filename.endswith("WA0035.jpg"):
                continue
            target.writestr(info, source.read(info))

    site_root = _bootstrap_site(tmp_path)
    _install_pipeline_stubs(monkeypatch, [])

    results = process_whatsapp_export(
        zip_path=corrupted_zip,
        output_dir=site_root,
        step_size=100,
        step_unit="messages",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    assert results is not None


def test_pipeline_rejects_unsafe_zip(tmp_path: Path):
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as archive:
        archive.writestr("../etc/passwd", "malicious content")

    with (
        pytest.raises(ZipValidationError, match="path traversal"),
        zipfile.ZipFile(malicious_zip) as archive,
    ):
        validate_zip_contents(archive)


def test_parser_enforces_message_schema(whatsapp_fixture: WhatsAppFixture):
    """Test that parser strictly enforces MESSAGE_SCHEMA without extra columns."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    # Verify table only has MESSAGE_SCHEMA columns (including message_id)
    expected_columns = {
        "timestamp",
        "date",
        "author",
        "message",
        "original_line",
        "tagged_line",
        "message_id",
    }
    assert set(table.columns) == expected_columns

    # Verify no extra columns
    assert "time" not in table.columns
    assert "group_slug" not in table.columns
    assert "group_name" not in table.columns


def test_enrichment_handles_schema_mismatch(
    whatsapp_fixture: WhatsAppFixture,
    tmp_path: Path,
):
    """Test that enrichment can handle extra columns not in CONVERSATION_SCHEMA."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_source(export, timezone=whatsapp_fixture.timezone)

    # Add extra columns to simulate the schema mismatch
    table = table.mutate(
        time=table.timestamp.strftime("%H:%M:%S"),
        group_slug=ibis.literal("test-group"),
        group_name=ibis.literal("Test Group"),
    )

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
    )

    cache = EnrichmentCache(tmp_path / "cache")

    # MODERN (Phase 2): Create config and context
    config = create_default_config(tmp_path)
    config = config.model_copy(
        deep=True,
        update={
            "enrichment": config.enrichment.model_copy(update={"enable_url": False}),
        },
    )

    enrichment_context = EnrichmentRuntimeContext(
        cache=cache,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
    )

    try:
        # This should not raise an exception
        enriched = enrich_table(
            updated_table,
            media_mapping,
            config=config,
            context=enrichment_context,
        )
        # Verify that the new rows have been added
        assert enriched.count().execute() > updated_table.count().execute()
        assert "egregora" in enriched.author.execute().tolist()

    finally:
        cache.close()
