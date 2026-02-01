import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker
from egregora.config.settings import EgregoraConfig, EnrichmentSettings


class TestEnrichmentWorkerStaging(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_zip = Path(self.temp_dir.name) / "input.zip"

        # Create a dummy zip file
        with zipfile.ZipFile(self.input_zip, "w") as zf:
            zf.writestr("small.txt", "small content")
            zf.writestr("large.mp4", "dummy content")

        self.mock_ctx = MagicMock(spec=EnrichmentRuntimeContext)
        self.mock_ctx.input_path = self.input_zip
        self.mock_ctx.site_root = Path(self.temp_dir.name)
        self.mock_ctx.config = MagicMock(spec=EgregoraConfig)
        self.mock_ctx.config.enrichment = MagicMock(spec=EnrichmentSettings)
        self.mock_ctx.config.enrichment.max_concurrent_enrichments = 1
        self.mock_ctx.config.enrichment.large_file_threshold_mb = 20
        self.mock_ctx.task_store = MagicMock()

        self.env_patcher = patch.dict(os.environ, {"GOOGLE_API_KEY": "fake_key"})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    @patch("egregora.agents.enricher.worker.zipfile.ZipFile")
    def test_staging_and_large_file_handling(self, mock_zip_cls):
        mock_zf = MagicMock()
        mock_zip_cls.return_value = mock_zf

        info_small = zipfile.ZipInfo("small.txt")
        info_large = zipfile.ZipInfo("large.mp4")
        mock_zf.infolist.return_value = [info_small, info_large]

        # Mock open context manager
        mock_source = MagicMock()
        # copyfileobj calls read(). If we return b"", it finishes.
        mock_source.read.return_value = b""

        # We need independent mocks for subsequent calls (large file)
        # side_effect for __enter__ to return different mocks?
        mock_zf.open.return_value.__enter__.return_value = mock_source

        worker = EnrichmentWorker(self.mock_ctx)

        tasks = [
            {
                "task_id": "task_small",
                "payload": {
                    "filename": "small.txt",
                    "media_type": "text/plain",
                    "original_filename": "small.txt",
                },
            },
            {
                "task_id": "task_large",
                "payload": {
                    "filename": "large.mp4",
                    "media_type": "video/mp4",
                    "original_filename": "large.mp4",
                },
            },
        ]

        # To avoid FileNotFoundError, we need _stage_file to actually create files.
        # But we mocked zf.open. shutil.copyfileobj reads from mock.
        # If mock_source.read returns b"", it writes nothing. File created (size 0).
        # This is fine.

        # KEY FIX: We need to mock Path.stat ONLY for size check, preserving other behavior.
        # Instead of patching Path.stat globally, we can mock _prepare_media_content's size check?
        # No, it calls file_path.stat().st_size directly.

        # We use a wrapper around the real stat.
        real_stat = Path.stat

        def fake_stat(self, *args, **kwargs):
            s = real_stat(self, *args, **kwargs)
            # If the file exists, we can return a mock that wraps the real stat result
            # but overrides st_size for our target files.
            if "large.mp4" in str(self):
                m = MagicMock(wraps=s)
                m.st_size = 30 * 1024 * 1024
                m.st_mode = s.st_mode
                return m
            # For small, we let it be 0 (or real size), which is < 20MB.
            return s

        with patch("pathlib.Path.stat", side_effect=fake_stat, autospec=True):
            with patch("google.genai.Client") as mock_client:
                mock_client_instance = mock_client.return_value
                mock_client_instance.files.upload.return_value = MagicMock(uri="http://file-uri")

                requests, _task_map = worker.media_handler._prepare_requests(tasks)

                self.assertEqual(len(requests), 2)

                req_large = next(r for r in requests if r["tag"] == "task_large")
                self.assertTrue(any("fileData" in p for p in req_large["contents"][0]["parts"]))

                mock_client_instance.files.upload.assert_called()
