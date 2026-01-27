"""Tests for enrichment configuration validation."""

import pytest
<<<<<<< HEAD

from egregora.config.exceptions import InvalidEnrichmentConfigError
from egregora.config.settings import PipelineEnrichmentConfig

=======
from egregora.config.settings import PipelineEnrichmentConfig
from egregora.config.exceptions import InvalidEnrichmentConfigError
>>>>>>> origin/pr/2747

def test_pipeline_enrichment_config_valid():
    """Test valid enrichment config."""
    config = PipelineEnrichmentConfig(batch_threshold=10, max_enrichments=100)
    assert config.batch_threshold == 10
    assert config.max_enrichments == 100

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2747
def test_pipeline_enrichment_config_invalid_batch_threshold():
    """Test invalid batch threshold."""
    with pytest.raises(InvalidEnrichmentConfigError, match="batch_threshold must be >= 1"):
        PipelineEnrichmentConfig(batch_threshold=0)

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2747
def test_pipeline_enrichment_config_invalid_max_enrichments():
    """Test invalid max enrichments."""
    with pytest.raises(InvalidEnrichmentConfigError, match="max_enrichments must be >= 0"):
        PipelineEnrichmentConfig(max_enrichments=-1)
