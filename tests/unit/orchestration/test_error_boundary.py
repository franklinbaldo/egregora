"""Tests for the ErrorBoundary implementation."""

import logging
from unittest.mock import ANY, Mock

import pytest
from egregora.exceptions import EgregoraError
from egregora.orchestration.error_boundary import DefaultErrorBoundary


class TestDefaultErrorBoundary:
    def test_handle_journal_error_fatal(self):
        logger = Mock(spec=logging.Logger)
        boundary = DefaultErrorBoundary(logger)

        # Should re-raise EgregoraError
        with pytest.raises(EgregoraError):
            boundary.handle_journal_error(EgregoraError("Fatal"))

        # Should wrap other exceptions in RuntimeError
        with pytest.raises(RuntimeError, match="Cannot proceed without journal"):
            boundary.handle_journal_error(ValueError("Bad value"))

        logger.critical.assert_called()

    def test_handle_enrichment_error_warns(self):
        logger = Mock(spec=logging.Logger)
        boundary = DefaultErrorBoundary(logger)

        # Should not raise
        boundary.handle_enrichment_error(ValueError("Failed"))

        logger.warning.assert_called_with("Enrichment failed: %s", ANY)

    def test_handle_rag_error_warns(self):
        logger = Mock(spec=logging.Logger)
        boundary = DefaultErrorBoundary(logger)

        # Should not raise
        boundary.handle_rag_error(ValueError("Failed"))

        logger.warning.assert_called_with("RAG error: %s", ANY)

    def test_handle_writer_error_fatal(self):
        logger = Mock(spec=logging.Logger)
        boundary = DefaultErrorBoundary(logger)

        exc = ValueError("Fatal writer")
        with pytest.raises(ValueError, match="Fatal writer"):
            boundary.handle_writer_error(exc)

        logger.error.assert_called_with("Writer error: %s", exc)

    def test_handle_generic_error_fatal(self):
        logger = Mock(spec=logging.Logger)
        boundary = DefaultErrorBoundary(logger)

        exc = RuntimeError("Fatal generic")
        with pytest.raises(RuntimeError, match="Fatal generic"):
            boundary.handle_generic_error(exc)

        logger.critical.assert_called_with("Pipeline error: %s", exc)
