from pathlib import Path

import pytest

from egregora.output_sinks.base import (
    BaseOutputSink,
    OutputSinkRegistry,
    create_output_sink,
)
from egregora.output_sinks.exceptions import (
    AdapterNotDetectedError,
    FilenameGenerationError,
    RegistryNotProvidedError,
)


# A dummy implementation of the abstract class for testing concrete methods
class DummySink(BaseOutputSink):
    def persist(self, document):
        pass

    def get(self, doc_type, identifier):
        pass

    @property
    def url_convention(self):
        pass

    @property
    def format_type(self):
        pass

    def supports_site(self, site_root):
        pass

    def get_markdown_extensions(self):
        pass

    def get_format_instructions(self):
        pass

    def initialize(self, site_root):
        pass

    def documents(self):
        return iter([])


def test_generate_unique_filename_raises_error_after_max_attempts(tmp_path):
    """
    Given a directory with conflicting filenames
    When generate_unique_filename is called and cannot find a unique name
    Then it should raise a FilenameGenerationError.
    """
    filename_pattern = "test{suffix}.txt"
    max_attempts = 3
    # Create conflicting files to exhaust attempts
    (tmp_path / "test.txt").touch()
    for i in range(2, max_attempts + 3):
        (tmp_path / f"test-{i}.txt").touch()

    with pytest.raises(FilenameGenerationError) as excinfo:
        BaseOutputSink.generate_unique_filename(tmp_path, filename_pattern, max_attempts=max_attempts)

    assert excinfo.value.pattern == filename_pattern
    assert excinfo.value.max_attempts == max_attempts


def test_create_output_sink_raises_error_if_registry_is_none():
    """
    Given a call to create_output_sink without a registry
    When the function is called
    Then it should raise a RegistryNotProvidedError.
    """
    with pytest.raises(RegistryNotProvidedError):
        create_output_sink(site_root=Path("/fake/path"), registry=None)


def test_finalize_window_runs_without_error():
    """
    Given a DummySink instance
    When finalize_window is called
    Then it should run without raising any errors.
    """
    sink = DummySink()
    # Pytest will fail the test if an exception is raised, so the try/except
    # block is not necessary.
    sink.finalize_window(
        window_label="test_window",
        _posts_created=["post1", "post2"],
        profiles_updated=["profile1"],
        metadata={},
    )


class TestOutputSinkRegistry:
    def test_detect_format_raises_error_when_no_adapter_found(self):
        """
        Given an empty OutputSinkRegistry
        When detect_format is called
        Then it should raise an AdapterNotDetectedError.
        """
        registry = OutputSinkRegistry()
        site_root = Path("/non/existent/site")

        with pytest.raises(AdapterNotDetectedError) as excinfo:
            registry.detect_format(site_root)

        assert excinfo.value.site_root == str(site_root)
