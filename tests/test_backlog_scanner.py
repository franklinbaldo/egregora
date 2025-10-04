"""Tests for backlog zip scanning utilities."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.backlog.scanner import scan_pending_days
from test_framework.helpers import create_test_zip


def _create_zip(day: date, directory: Path, content: str = "Mensagem") -> Path:
    zip_path = directory / f"{day.isoformat()}.zip"
    create_test_zip(content, zip_path)
    return zip_path


def test_scan_finds_all_zips(tmp_path: Path) -> None:
    zip_dir = tmp_path / "zips"
    output_dir = tmp_path / "out"
    zip_dir.mkdir()
    output_dir.mkdir()

    days = [date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3)]
    for day in days:
        _create_zip(day, zip_dir, content=f"{day.strftime('%d/%m/%Y')} 09:00 - Alice: Teste")

    pending = scan_pending_days(zip_dir, output_dir)
    assert len(pending) == len(days)
    assert [item.date for item in pending] == days


def test_scan_identifies_pending_days(tmp_path: Path) -> None:
    zip_dir = tmp_path / "zips"
    output_dir = tmp_path / "out"
    zip_dir.mkdir()
    output_dir.mkdir()

    processed_day = date(2024, 10, 1)
    pending_day = date(2024, 10, 2)

    _create_zip(processed_day, zip_dir, content="01/10/2024 09:00 - Alice: ok")
    _create_zip(pending_day, zip_dir, content="02/10/2024 09:00 - Bob: ok")

    (output_dir / f"{processed_day.isoformat()}.md").write_text("newsletter pronta")

    pending = scan_pending_days(zip_dir, output_dir)
    processed_entry = next(item for item in pending if item.date == processed_day)
    pending_entry = next(item for item in pending if item.date == pending_day)

    assert processed_entry.already_processed is True
    assert pending_entry.already_processed is False


def test_scan_ignores_malformed_filenames(tmp_path: Path) -> None:
    zip_dir = tmp_path / "zips"
    output_dir = tmp_path / "out"
    zip_dir.mkdir()
    output_dir.mkdir()

    _create_zip(date(2024, 10, 1), zip_dir)
    create_test_zip("conteúdo", zip_dir / "invalid-name.zip")

    pending = scan_pending_days(zip_dir, output_dir)
    assert len(pending) == 1
    assert pending[0].date == date(2024, 10, 1)


def test_scan_extracts_basic_statistics(tmp_path: Path) -> None:
    zip_dir = tmp_path / "zips"
    output_dir = tmp_path / "out"
    zip_dir.mkdir()
    output_dir.mkdir()

    content = """01/10/2024 09:00 - Alice: Olá\n01/10/2024 09:01 - Bob: https://example.com\n01/10/2024 09:02 - Alice: Tchau"""
    _create_zip(date(2024, 10, 1), zip_dir, content=content)

    pending = scan_pending_days(zip_dir, output_dir)
    assert pending[0].message_count == 3
    assert pending[0].url_count == 1
    assert pending[0].participant_count == 2


def test_scan_orders_results_chronologically(tmp_path: Path) -> None:
    zip_dir = tmp_path / "zips"
    output_dir = tmp_path / "out"
    zip_dir.mkdir()
    output_dir.mkdir()

    _create_zip(date(2024, 10, 3), zip_dir)
    _create_zip(date(2024, 10, 1), zip_dir)
    _create_zip(date(2024, 10, 2), zip_dir)

    pending = scan_pending_days(zip_dir, output_dir)
    assert [item.date for item in pending] == [date(2024, 10, 1), date(2024, 10, 2), date(2024, 10, 3)]
