"""Enrichment system tests using WhatsApp test data."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import EnrichmentConfig
import polars as pl

from egregora.enrichment import ContentEnricher, URL_RE, EnrichmentResult
from egregora.cache_manager import CacheManager
from test_framework.helpers import TestDataGenerator


_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<time>\d{1,2}:\d{2})\s*-\s*(?P<rest>.+)$"
)


def _transcripts_to_frame(
    transcripts: Sequence[tuple[date, str]]
) -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    for provided_date, transcript in transcripts:
        base_dt = datetime.combine(provided_date, time.min)
        offset = 0
        for raw_line in transcript.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            match = _LINE_PATTERN.match(line)
            if match:
                date_str = match.group("date")
                time_str = match.group("time")
                rest = match.group("rest")
                try:
                    parsed_dt = datetime.strptime(
                        f"{date_str} {time_str}", "%d/%m/%Y %H:%M"
                    )
                except ValueError:
                    parsed_dt = base_dt + timedelta(minutes=offset)
                if ": " in rest:
                    author, message = rest.split(": ", 1)
                else:
                    author, message = "", rest
                rows.append(
                    {
                        "date": parsed_dt.date(),
                        "timestamp": parsed_dt,
                        "author": author,
                        "message": message,
                    }
                )
            else:
                current_dt = base_dt + timedelta(minutes=offset)
                rows.append(
                    {
                        "date": current_dt.date(),
                        "timestamp": current_dt,
                        "author": "",
                        "message": line,
                    }
                )
            offset += 1

    if not rows:
        return pl.DataFrame(
            {
                "date": [transcripts[0][0]],
                "timestamp": [datetime.combine(transcripts[0][0], time.min)],
                "author": [""],
                "message": [transcripts[0][1]],
            }
        )

    return pl.DataFrame(rows)


class MockGeminiModel:
    def __init__(self, relevance=5, error=None):
        self.call_count = 0
        self.relevance = relevance
        self.error = error

    def generate_content(self, model, contents, config):
        self.call_count += 1
        if self.error:
            raise self.error

        response_data = {
            "summary": "Mocked summary",
            "topics": ["Point 1", "Point 2"],
            "actions": [
                {
                    "description": "Revisar conteúdo compartilhado",
                    "owner": "time",
                }
            ],
        }
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = json.dumps(response_data)
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mock_response.text = mock_part.text
        return mock_response


class MockGeminiClient:
    def __init__(self, relevance=5, error=None):
        self.models = MockGeminiModel(relevance, error)

    @property
    def call_count(self):
        return self.models.call_count


def test_parse_response_with_valid_json():
    payload = {
        "summary": "Conteúdo estruturado",
        "key_points": ["a", "b"],
        "tone": "positivo",
        "relevance": 4,
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(payload)

    analysis = ContentEnricher._parse_response(mock_response)

    assert analysis.summary == payload["summary"]
    assert analysis.key_points == payload["key_points"]
    assert analysis.tone == payload["tone"]
    assert analysis.relevance == payload["relevance"]
    assert analysis.raw_response == mock_response.text


def test_parse_response_falls_back_to_plain_text():
    mock_response = MagicMock()
    mock_response.text = "Resposta sem JSON estruturado"

    analysis = ContentEnricher._parse_response(mock_response)

    assert analysis.summary == "Resposta sem JSON estruturado"
    assert analysis.key_points == []
    assert analysis.relevance == 1


def test_parse_response_handles_missing_payload():
    mock_response = MagicMock()
    mock_response.text = None
    mock_response.candidates = []

    analysis = ContentEnricher._parse_response(mock_response)

    assert analysis.error == "Resposta vazia do modelo."
    assert analysis.relevance == 1

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_content_enrichment_with_whatsapp_urls(mock_guess_type, tmp_path):
    conversation_with_urls = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(
        enabled=True,
        max_concurrent_analyses=2,
        metrics_csv_path=tmp_path / "metrics.csv",
    )
    cache_manager = CacheManager(tmp_path / "cache", size_limit_mb=10)
    mock_client = MockGeminiClient()

    enricher = ContentEnricher(config, cache_manager=cache_manager)
    transcripts = [(date.today(), conversation_with_urls)]
    frame = _transcripts_to_frame(transcripts)
    result = asyncio.run(
        enricher.enrich_dataframe(frame, client=mock_client)
    )

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) >= 1
    assert result.items[0].analysis is not None
    assert result.items[0].analysis.summary == "Mocked summary"
    assert result.items[0].analysis.topics == ["Point 1", "Point 2"]
    assert [item.description for item in result.items[0].analysis.actions] == [
        "Revisar conteúdo compartilhado"
    ]

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_enrichment_caching_functionality(mock_guess_type, tmp_path):
    test_url = "https://example.com/test-article"
    transcript = [(date.today(), f"Check this out: {test_url}")]
    config = EnrichmentConfig(enabled=True, metrics_csv_path=tmp_path / "metrics.csv")
    cache_manager = CacheManager(tmp_path / "cache", size_limit_mb=10)
    mock_client = MockGeminiClient()

    enricher = ContentEnricher(config, cache_manager=cache_manager)
    frame = _transcripts_to_frame(transcript)
    asyncio.run(enricher.enrich_dataframe(frame, client=mock_client))
    assert mock_client.call_count == 1

    frame = _transcripts_to_frame(transcript)
    asyncio.run(enricher.enrich_dataframe(frame, client=mock_client))
    assert mock_client.call_count == 1

def test_media_placeholder_handling(tmp_path):
    content_with_media = "09:46 - Franklin: <mídia oculta>"
    config = EnrichmentConfig(enabled=True, metrics_csv_path=tmp_path / "metrics.csv")
    enricher = ContentEnricher(config)
    transcripts = [(date.today(), content_with_media)]
    frame = _transcripts_to_frame(transcripts)
    result = asyncio.run(enricher.enrich_dataframe(frame, client=None))

    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 1
    assert result.items[0].reference.is_media_placeholder
    assert "Mídia sem descrição" in result.items[0].analysis.summary

def test_enrichment_with_disabled_config(tmp_path):
    conversation = TestDataGenerator.create_complex_conversation()
    config = EnrichmentConfig(enabled=False, metrics_csv_path=tmp_path / "metrics.csv")
    enricher = ContentEnricher(config)
    frame = _transcripts_to_frame([(date.today(), conversation)])
    result = asyncio.run(enricher.enrich_dataframe(frame, client=None))
    assert isinstance(result, EnrichmentResult)
    assert len(result.items) == 0

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_error_handling_in_enrichment(mock_guess_type, tmp_path):
    config = EnrichmentConfig(enabled=True, metrics_csv_path=tmp_path / "metrics.csv")
    transcript = [(date.today(), "https://example.com/failing-url")]
    mock_client = MockGeminiClient(error=Exception("API Error"))

    enricher = ContentEnricher(config)
    frame = _transcripts_to_frame(transcript)
    result = asyncio.run(enricher.enrich_dataframe(frame, client=mock_client))

    assert len(result.errors) == 1
    assert "API Error" in result.errors[0]

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_concurrent_url_processing(mock_guess_type, tmp_path):
    content = "https://a.com\nhttps://b.com\nhttps://c.com"
    config = EnrichmentConfig(
        enabled=True,
        max_concurrent_analyses=3,
        metrics_csv_path=tmp_path / "metrics.csv",
    )
    mock_client = MockGeminiClient()
    enricher = ContentEnricher(config)
    frame = _transcripts_to_frame([(date.today(), content)])
    result = asyncio.run(enricher.enrich_dataframe(frame, client=mock_client))
    assert len(result.items) == 3
    assert mock_client.call_count == 3

@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_relevance_filtering(mock_guess_type, tmp_path):
    config = EnrichmentConfig(enabled=True, relevance_threshold=3)
    content = "https://low.com\nhttps://high.com"

    class VarRelevanceClient:
        def __init__(self):
            self.models = self
            self.calls = 0
        def generate_content(self, model, contents, config):
            self.calls += 1
            prompt_text = contents[0].parts[0].text
            is_low = '"url": "https://low.com"' in prompt_text
            response_data = {
                "summary": "Resumo",
                "topics": [] if is_low else ["Tema"],
                "actions": [],
            }
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.text = json.dumps(response_data)
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
            mock_response.text = mock_part.text
            return mock_response

    mock_client = VarRelevanceClient()
    enricher = ContentEnricher(
        config.model_copy(update={"metrics_csv_path": tmp_path / "metrics.csv"})
    )
    frame = _transcripts_to_frame([(date.today(), content)])
    result = asyncio.run(enricher.enrich_dataframe(frame, client=mock_client))

    assert len(result.items) == 2
    relevant_items = result.relevant_items(config.relevance_threshold)
    assert len(relevant_items) == 1
    assert relevant_items[0].analysis.relevance >= 3


@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_enrich_with_real_transcript_and_metrics(mock_guess_type, tmp_path):
    transcript_path = Path(__file__).parent / "data" / "Conversa do WhatsApp com Teste.txt"
    raw_text = transcript_path.read_text(encoding="utf-8")

    processed_lines: list[str] = []
    for raw_line in raw_text.splitlines():
        parts = raw_line.split(" - ", 1)
        if len(parts) != 2:
            continue
        timestamp_block, message = parts
        pieces = timestamp_block.strip().split()
        if not pieces:
            continue
        time_value = pieces[-1]
        processed_lines.append(f"{time_value} - {message.strip()}")

    transcript = "\n".join(processed_lines)
    metrics_path = tmp_path / "metrics.csv"
    config = EnrichmentConfig(
        enabled=True,
        max_links=5,
        metrics_csv_path=metrics_path,
    )
    mock_client = MockGeminiClient(relevance=4)
    enricher = ContentEnricher(config)

    frame = _transcripts_to_frame([(date(2025, 10, 3), transcript)])
    result = asyncio.run(
        enricher.enrich_dataframe(frame, client=mock_client)
    )

    assert result.errors == []
    assert result.duration_seconds >= 0
    assert result.metrics is not None

    metrics = result.metrics
    assert metrics is not None
    assert metrics.total_references >= 1
    assert metrics.analyzed_items == len(result.items)
    assert metrics.relevant_items == len(
        result.relevant_items(config.relevance_threshold)
    )
    assert any("youtu" in domain for domain in metrics.domains)

    assert metrics_path.exists()
    with metrics_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[-1]["relevant_items"] == str(metrics.relevant_items)


def test_example_enrichment_script_runs_with_stub(tmp_path):
    metrics_path = tmp_path / "metrics.csv"
    env = os.environ.copy()
    pythonpath_parts = [
        str(Path(__file__).resolve().parents[1] / "src"),
        str(Path(__file__).resolve().parents[0] / "stubs"),
        env.get("PYTHONPATH", ""),
    ]
    env["PYTHONPATH"] = os.pathsep.join(part for part in pythonpath_parts if part)
    env["GEMINI_API_KEY"] = "offline-key"
    env["FAKE_GEMINI_RESPONSE"] = json.dumps(
        {
            "summary": "Smoke test response",
            "key_points": ["Ponto 1"],
            "tone": "claro",
            "relevance": 3,
        },
        ensure_ascii=False,
    )
    env["EGREGORA_METRICS_PATH"] = str(metrics_path)
    env["EGREGORA_ENRICHMENT_OFFLINE"] = "1"

    result = subprocess.run(
        [sys.executable, "example_enrichment.py"],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "✅" in result.stdout
    assert metrics_path.exists()


if __name__ == "__main__":
    # Manual test runner
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        
        print("Running enrichment tests...")
        
        try:
            test_url_extraction_whatsapp_content(temp_dir)
            print("✓ URL extraction test passed")
            
            test_whatsapp_message_parsing(temp_dir)
            print("✓ Message parsing test passed")
            
            test_content_enrichment_with_whatsapp_urls(temp_dir)
            print("✓ Content enrichment test passed")
            
            test_enrichment_caching_functionality(temp_dir)
            print("✓ Caching test passed")
            
            test_media_placeholder_handling(temp_dir)
            print("✓ Media placeholder test passed")
            
            test_enrichment_with_disabled_config(temp_dir)
            print("✓ Disabled config test passed")
            
            test_error_handling_in_enrichment(temp_dir)
            print("✓ Error handling test passed")
            
            test_concurrent_url_processing(temp_dir)
            print("✓ Concurrent processing test passed")
            
            test_relevance_filtering(temp_dir)
            print("✓ Relevance filtering test passed")
            
            print("\n🎉 All enrichment tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()