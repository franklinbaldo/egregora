"""Unit tests for the enrichment agent's logic."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from egregora.agents.enricher import EnrichmentWorker, _normalize_slug, load_file_as_binary_content
from egregora.agents.exceptions import MediaStagingError


class TestEnrichmentWorkerStageFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_ctx = MagicMock()
        self.mock_ctx.input_path = Path(self.temp_dir.name) / "archive.zip"
        self.worker = EnrichmentWorker(ctx=self.mock_ctx)

    def tearDown(self):
        self.worker.close()
        self.temp_dir.cleanup()

    def test_stage_file_success(self):
        """Test successful staging of a file from a ZIP archive."""
        zip_path = self.mock_ctx.input_path
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test_file.txt", "some content")

        worker = EnrichmentWorker(ctx=self.mock_ctx)
        task = {"task_id": "123"}
        payload = {
            "filename": "test_file.txt",
            "original_filename": "test_file.txt",
        }
        staged_path = worker._stage_file(task, payload)

        self.assertTrue(staged_path.exists())
        self.assertIn("123_test_file.txt", str(staged_path))
        with staged_path.open() as f:
            self.assertEqual(f.read(), "some content")
        worker.close()

    def test_stage_file_zip_not_found(self):
        """Test MediaStagingError is raised when the ZIP file does not exist."""
        self.mock_ctx.input_path = Path(self.temp_dir.name) / "non_existent.zip"
        worker = EnrichmentWorker(ctx=self.mock_ctx)
        task = {"task_id": "123"}
        payload = {"filename": "test_file.txt"}

        with pytest.raises(MediaStagingError):
            worker._stage_file(task, payload)
        worker.close()

    def test_stage_file_corrupt_zip(self):
        """Test MediaStagingError is raised when the ZIP file is corrupt."""
        zip_path = self.mock_ctx.input_path
        with zip_path.open("w") as f:
            f.write("this is not a zip file")

        worker = EnrichmentWorker(ctx=self.mock_ctx)
        task = {"task_id": "123"}
        payload = {"filename": "test_file.txt"}

        with pytest.raises(MediaStagingError):
            worker._stage_file(task, payload)
        worker.close()

    def test_stage_file_no_filename_in_payload(self):
        """Test MediaStagingError is raised when filename is missing from payload."""
        zip_path = self.mock_ctx.input_path
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test_file.txt", "some content")

        worker = EnrichmentWorker(ctx=self.mock_ctx)
        task = {"task_id": "123"}
        payload = {}  # Empty payload

        with pytest.raises(MediaStagingError):
            worker._stage_file(task, payload)
        worker.close()


class TestEnrichmentWorkerClose(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_ctx = MagicMock()
        self.mock_ctx.input_path = Path(self.temp_dir.name) / "archive.zip"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_close_closes_zip_handle_and_cleans_up_staging_dir(self):
        """Verify that the close method closes the zip handle and cleans up the staging directory."""
        # Create a dummy zip file
        zip_path = self.mock_ctx.input_path
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test_file.txt", "some content")

        worker = EnrichmentWorker(ctx=self.mock_ctx)

        # Get a reference to the zip_handle and staging_dir before they are closed
        zip_handle = worker.zip_handle
        zip_handle.close = MagicMock()
        staging_dir = worker.staging_dir
        staging_dir.cleanup = MagicMock()

        # Call the close method
        worker.close()

        # Assert that the cleanup methods were called
        zip_handle.close.assert_called_once()
        staging_dir.cleanup.assert_called_once()


class TestNormalizeSlug(unittest.TestCase):
    def test_normalize_slug_valid(self):
        self.assertEqual(_normalize_slug("A Valid Slug", "id"), "a-valid-slug")

    def test_normalize_slug_none(self):
        with pytest.raises(ValueError, match="LLM failed to generate slug"):
            _normalize_slug(None, "id")

    def test_normalize_slug_empty(self):
        with pytest.raises(ValueError, match="LLM failed to generate slug"):
            _normalize_slug("  ", "id")

    def test_normalize_slug_invalid_after_slugify(self):
        with pytest.raises(ValueError, match="LLM slug .* is invalid after normalization"):
            _normalize_slug("!@#$", "id")

    def test_normalize_slug_post_is_invalid(self):
        """Test that 'post' is considered an invalid slug after normalization."""
        with pytest.raises(ValueError, match="LLM slug .* is invalid after normalization"):
            _normalize_slug("post", "some-identifier")


class TestLoadFileAsBinaryContent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = Path(self.temp_dir.name) / "test.txt"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_file_as_binary_content_success(self):
        with self.test_file.open("wb") as f:
            f.write(b"test content")

        binary_content = load_file_as_binary_content(self.test_file)
        self.assertEqual(binary_content.data, b"test content")
        self.assertEqual(binary_content.media_type, "text/plain")

    def test_load_file_as_binary_content_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_file_as_binary_content(Path(self.temp_dir.name) / "non_existent.txt")

    def test_load_file_as_binary_content_file_too_large(self):
        with self.test_file.open("wb") as f:
            f.write(b"a" * (21 * 1024 * 1024))  # 21MB

        with pytest.raises(ValueError, match=r"File too large: .* exceeds 20MB limit"):
            load_file_as_binary_content(self.test_file, max_size_mb=20)


class TestParseMediaResult(unittest.TestCase):
    def setUp(self):
        self.mock_ctx = MagicMock()
        self.worker = EnrichmentWorker(ctx=self.mock_ctx)
        self.worker.task_store = MagicMock()
        self.task = {"task_id": "media-task-1", "_parsed_payload": {"filename": "image.jpg"}}

    def test_parse_media_result_success(self):
        """Test successful parsing of a valid media result."""
        response_text = json.dumps(
            {
                "slug": "a-great-image",
                "markdown": "This is a great image.",
                "description": "A description.",
                "alt_text": "Alt text.",
            }
        )
        mock_res = MagicMock()
        mock_res.response = {"text": response_text}

        result = self.worker._parse_media_result(mock_res, self.task)

        self.assertIsNotNone(result)
        _payload, slug_value, markdown = result
        self.assertEqual(slug_value, "a-great-image")
        self.assertEqual(markdown, "This is a great image.")
        self.worker.task_store.mark_failed.assert_not_called()

    def test_parse_media_result_malformed_json(self):
        """Test that malformed JSON is handled correctly."""
        mock_res = MagicMock()
        mock_res.response = {"text": "{'bad-json':"}

        result = self.worker._parse_media_result(mock_res, self.task)

        self.assertIsNone(result)
        self.worker.task_store.mark_failed.assert_called_once()
        args, _ = self.worker.task_store.mark_failed.call_args
        self.assertEqual(args[0], "media-task-1")
        self.assertIn("Parse error", args[1])

    def test_parse_media_result_missing_slug(self):
        """Test that a missing slug is handled correctly."""
        response_text = json.dumps({"markdown": "some markdown"})
        mock_res = MagicMock()
        mock_res.response = {"text": response_text}

        result = self.worker._parse_media_result(mock_res, self.task)

        self.assertIsNone(result)
        self.worker.task_store.mark_failed.assert_called_once_with("media-task-1", "Missing slug or markdown")

    def test_parse_media_result_missing_markdown_with_fallback(self):
        """Test fallback markdown construction when 'markdown' is missing."""
        response_text = json.dumps(
            {
                "slug": "fallback-slug",
                "description": "A fallback description.",
                "alt_text": "Fallback alt text.",
            }
        )
        mock_res = MagicMock()
        mock_res.response = {"text": response_text}

        self.task["_parsed_payload"]["filename"] = "test.png"

        result = self.worker._parse_media_result(mock_res, self.task)

        self.assertIsNotNone(result)
        _payload, slug_value, markdown = result
        self.assertEqual(slug_value, "fallback-slug")
        self.assertIn("A fallback description.", markdown)
        self.assertIn("![Fallback alt text.](fallback-slug.png)", markdown)
        self.worker.task_store.mark_failed.assert_not_called()

    def test_parse_media_result_missing_markdown_and_fallback(self):
        """Test failure when markdown and fallback fields are missing."""
        response_text = json.dumps({"slug": "no-content"})
        mock_res = MagicMock()
        mock_res.response = {"text": response_text}

        result = self.worker._parse_media_result(mock_res, self.task)

        self.assertIsNone(result)
        self.worker.task_store.mark_failed.assert_called_once_with("media-task-1", "Missing slug or markdown")


if __name__ == "__main__":
    unittest.main()
