from __future__ import annotations

import string
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import ibis
import pytest
from conftest import WhatsAppFixture

from egregora.augmentation.enrichment.core import enrich_table
from egregora.augmentation.enrichment.media import extract_and_replace_media
from egregora.ingestion.parser import filter_egregora_messages, parse_export
from egregora.orchestration.pipeline import process_whatsapp_export
from egregora.utils.batch import BatchPromptResult
from egregora.utils.cache import EnrichmentCache
from egregora.utils.zip import ZipValidationError, validate_zip_contents


def create_export_from_fixture(fixture: WhatsAppFixture):
    return fixture.create_export()


def _bootstrap_site(tmp_path: Path) -> Path:
    site_root = tmp_path / "site"
    docs_dir = site_root / "docs"
    posts_dir = docs_dir / "posts"
    profiles_dir = docs_dir / "profiles"
    media_dir = docs_dir / "media"

    posts_dir.mkdir(parents=True)
    profiles_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)

    mkdocs_path = site_root / "mkdocs.yml"
    mkdocs_path.write_text("site_name: Test Suite\n", encoding="utf-8")
    return site_root


class DummyBatchClient:
    def __init__(self, model: str):
        self.default_model = model
        self.uploaded: list[Path] = []

    def generate_content(self, requests, **kwargs):  # noqa: D401 - test helper
        """Return canned batch responses for enrichment pipelines."""

        results = []
        for request in requests:
            results.append(
                BatchPromptResult(
                    tag=getattr(request, "tag", None),
                    response=SimpleNamespace(text=f"Generated content for {getattr(request, 'tag', 'unknown')}"),
                    error=None,
                )
            )
        return results

    def embed_content(self, requests, **kwargs):  # pragma: no cover - unused in tests
        return []

    def upload_file(self, *, path: str, display_name: str | None = None):
        file_path = Path(path)
        self.uploaded.append(file_path)
        return SimpleNamespace(uri=f"stub://{file_path.name}", mime_type="image/jpeg")


class DummyGenaiClient:
    def __init__(self, *args, **kwargs):
        response = SimpleNamespace(candidates=[])
        self.models = SimpleNamespace(generate_content=lambda *a, **k: response)
        self.aio = SimpleNamespace(models=self.models)
        self.files = SimpleNamespace(upload=lambda *a, **k: SimpleNamespace(uri="stub://file", mime_type="image/jpeg"))
        dummy_job = SimpleNamespace(
            name="stub-job",
            dest=SimpleNamespace(inlined_responses=[]),
            state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
            done=True,
            error=None,
        )
        self.batches = SimpleNamespace(create=lambda *a, **k: dummy_job, get=lambda *a, **k: dummy_job)

    def close(self):  # pragma: no cover - compatibility shim
        return None


def _install_pipeline_stubs(monkeypatch, captured_dates: list[str]):
    monkeypatch.setattr("egregora.orchestration.pipeline.genai.Client", DummyGenaiClient)
    monkeypatch.setattr("egregora.orchestration.pipeline.GeminiBatchClient", lambda client, model, **kwargs: DummyBatchClient(model))

    def _stub_writer(
        table,
        period_key,
        client,
        batch_client,
        output_dir,
        profiles_dir,
        rag_dir,
        model_config,
        enable_rag=True,
        embedding_output_dimensionality=3072,
        *,
        retrieval_mode="exact",
        retrieval_nprobe=None,
        retrieval_overfetch=None,
    ):
        captured_dates.append(period_key)
        output_dir.mkdir(parents=True, exist_ok=True)
        profiles_dir.mkdir(parents=True, exist_ok=True)

        post_path = output_dir / f"{period_key}-stub.md"
        post_path.write_text(
            "---\n"
            f"title: Stub Post for {period_key}\n"
            f"date: {period_key}\n"
            "tags: []\n"
            "---\n"
            "This is a placeholder post used during testing.\n",
            encoding="utf-8",
        )

        profile_path = profiles_dir / "stub-profile.md"
        profile_path.write_text("stub profile", encoding="utf-8")

        return {"posts": [str(post_path)], "profiles": [str(profile_path)]}

    monkeypatch.setattr("egregora.orchestration.pipeline.write_posts_for_period", _stub_writer)


def test_zip_extraction_completes_without_error(whatsapp_fixture: WhatsAppFixture):
    zip_path = whatsapp_fixture.zip_path
    with zipfile.ZipFile(zip_path) as archive:
        validate_zip_contents(archive)
        members = archive.namelist()

    assert "Conversa do WhatsApp com Teste.txt" in members
    assert sum(1 for member in members if member.endswith(".jpg")) == 4


def test_parser_produces_valid_table(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    assert {"timestamp", "author", "message"}.issubset(table.columns)
    assert table.count().execute() == 10

    timestamps = table["timestamp"].execute()
    assert all(ts.tzinfo is not None for ts in timestamps)


def test_parser_handles_portuguese_dates(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)
    dates = [value.date() for value in table["date"].execute().tolist()]

    assert date(2025, 10, 28) in dates


def test_parser_preserves_all_messages(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    participant_rows = table.filter(~table.author.isin(["system", "egregora"]))
    assert participant_rows.count().execute() == 10


def test_parser_extracts_media_references(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    combined = " ".join(table["message"].execute().tolist())
    assert "IMG-20251028-WA0035.jpg" in combined
    assert "arquivo anexado" in combined


def test_anonymization_removes_real_author_names(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    authors = table["author"].execute().tolist()
    for forbidden in {"Franklin", "Iuri Brasil", "Você", "Eurico Max"}:
        assert forbidden not in authors

    messages = table["message"].execute().tolist()
    assert any("@" in message and "teste de menção" in message for message in messages)


def test_anonymization_is_deterministic(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table_one = parse_export(export, timezone=whatsapp_fixture.timezone)
    table_two = parse_export(export, timezone=whatsapp_fixture.timezone)

    authors_one = sorted(table_one.select("author").distinct().execute()["author"].tolist())
    authors_two = sorted(table_two.select("author").distinct().execute()["author"].tolist())

    assert authors_one == authors_two


def test_anonymized_uuids_are_valid_format(whatsapp_fixture: WhatsAppFixture):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    distinct_authors = table.select("author").distinct().execute()["author"].tolist()
    authors = [value for value in distinct_authors if value not in {"system", "egregora"}]
    valid_chars = set(string.hexdigits.lower())
    for author_id in authors:
        assert len(author_id) == 8
        assert set(author_id) <= valid_chars


def test_media_extraction_creates_expected_files(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    _, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
        str(export.group_slug),
    )

    assert len(media_mapping) == 4
    for extracted_path in media_mapping.values():
        assert extracted_path.exists()


def test_media_references_replaced_in_messages(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, _ = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
        str(export.group_slug),
    )

    joined_messages = " ".join(updated_table["message"].execute().dropna().tolist())
    assert "![Image]" in joined_messages


def test_media_files_have_deterministic_names(whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    docs_dir_one = tmp_path / "docs1"
    docs_dir_two = tmp_path / "docs2"
    posts_one = docs_dir_one / "posts"
    posts_two = docs_dir_two / "posts"
    docs_dir_one.mkdir()
    docs_dir_two.mkdir()
    posts_one.mkdir()
    posts_two.mkdir()

    _, mapping_one = extract_and_replace_media(table, export.zip_path, docs_dir_one, posts_one, str(export.group_slug))
    _, mapping_two = extract_and_replace_media(table, export.zip_path, docs_dir_two, posts_two, str(export.group_slug))

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
        period="day",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    assert results
    assert processed_dates == ["2025-10-28"]


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
        period="day",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    docs_dir = site_root / "docs"
    assert (docs_dir / "posts").exists()
    assert (docs_dir / "profiles").exists()
    assert (docs_dir / "media").exists()
    assert (site_root / "enriched").exists()


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
        period="day",
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
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

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
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    docs_dir = tmp_path / "docs"
    posts_dir = docs_dir / "posts"
    docs_dir.mkdir()
    posts_dir.mkdir()

    updated_table, media_mapping = extract_and_replace_media(
        table,
        export.zip_path,
        docs_dir,
        posts_dir,
        str(export.group_slug),
    )

    cache = EnrichmentCache(tmp_path / "cache")
    text_client = DummyBatchClient("text-model")
    vision_client = DummyBatchClient("vision-model")

    try:
        enriched = enrich_table(
            updated_table,
            media_mapping,
            text_client,
            vision_client,
            cache,
            docs_dir,
            posts_dir,
            enable_url=False,
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
    with zipfile.ZipFile(whatsapp_fixture.zip_path) as source, zipfile.ZipFile(corrupted_zip, "w") as target:
        for info in source.infolist():
            if info.filename.endswith("WA0035.jpg"):
                continue
            target.writestr(info, source.read(info))

    site_root = _bootstrap_site(tmp_path)
    _install_pipeline_stubs(monkeypatch, [])

    results = process_whatsapp_export(
        zip_path=corrupted_zip,
        output_dir=site_root,
        period="day",
        enable_enrichment=False,
        timezone=whatsapp_fixture.timezone,
        gemini_api_key=gemini_api_key,
    )

    assert results is not None


def test_pipeline_rejects_unsafe_zip(tmp_path: Path):
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as archive:
        archive.writestr("../etc/passwd", "malicious content")

    with pytest.raises(ZipValidationError, match="path traversal"):
        with zipfile.ZipFile(malicious_zip) as archive:
            validate_zip_contents(archive)


def test_parser_enforces_message_schema(whatsapp_fixture: WhatsAppFixture):
    """Test that parser strictly enforces MESSAGE_SCHEMA without extra columns."""
    export = create_export_from_fixture(whatsapp_fixture)
    table = parse_export(export, timezone=whatsapp_fixture.timezone)

    # Verify table only has MESSAGE_SCHEMA columns
    expected_columns = {"timestamp", "date", "author", "message", "original_line", "tagged_line"}
    assert set(table.columns) == expected_columns

    # Verify no extra columns
    assert "time" not in table.columns
    assert "group_slug" not in table.columns
    assert "group_name" not in table.columns
