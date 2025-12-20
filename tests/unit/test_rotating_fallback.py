"""Tests for RotatingFallbackModel rotation timing.

Verifies that API key/model rotation on 429 errors happens immediately
(less than 1 second) without artificial delays.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model

from egregora.models.rotating_fallback import RotatingFallbackModel


class MockModel(Model):
    """Mock model that can be configured to raise 429 or succeed."""

    def __init__(self, name: str, fail_count: int = 0) -> None:
        self._name = name
        self._fail_count = fail_count
        self._call_count = 0

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def system(self) -> str | None:
        return None

    async def request(self, messages, model_settings, model_request_parameters):
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise ModelHTTPError(status_code=429, model_name=self._name, body=None)
        # Return a mock response
        return MagicMock()

    async def request_stream(self, messages, model_settings, model_request_parameters):
        raise NotImplementedError("Stream not needed for this test")


@pytest.mark.asyncio
async def test_rotation_happens_in_under_one_second():
    """Test that rotation on 429 happens immediately, not with a delay."""
    # Create models where the first one always fails with 429
    model1 = MockModel("model-key1", fail_count=999)  # Always fails
    model2 = MockModel("model-key2", fail_count=0)  # Always succeeds

    rotating_model = RotatingFallbackModel([model1, model2])

    # Measure time for the request (which should rotate on 429)
    start_time = time.monotonic()
    response = await rotating_model.request(
        messages=[],
        model_settings=None,
        model_request_parameters=MagicMock(),
    )
    elapsed_time = time.monotonic() - start_time

    # Verify:
    # 1. The request succeeded (didn't raise)
    assert response is not None

    # 2. Model 1 was called (and got 429)
    assert model1._call_count == 1

    # 3. Model 2 was called (and succeeded)
    assert model2._call_count == 1

    # 4. CRITICAL: Rotation happened in under 1 second (no artificial delay)
    assert elapsed_time < 1.0, f"Rotation took {elapsed_time:.2f}s, expected < 1s"


@pytest.mark.asyncio
async def test_rotation_through_multiple_keys_is_fast():
    """Test that rotating through multiple failing keys is still fast."""
    # Create 4 models where first 3 fail, 4th succeeds
    models = [
        MockModel("model-key1", fail_count=999),
        MockModel("model-key2", fail_count=999),
        MockModel("model-key3", fail_count=999),
        MockModel("model-key4", fail_count=0),
    ]

    rotating_model = RotatingFallbackModel(models)

    start_time = time.monotonic()
    response = await rotating_model.request(
        messages=[],
        model_settings=None,
        model_request_parameters=MagicMock(),
    )
    elapsed_time = time.monotonic() - start_time

    # All 4 models should have been tried
    assert models[0]._call_count == 1
    assert models[1]._call_count == 1
    assert models[2]._call_count == 1
    assert models[3]._call_count == 1

    # Total rotation through 3 failing keys should still be under 1 second
    assert elapsed_time < 1.0, f"3 rotations took {elapsed_time:.2f}s, expected < 1s"
    assert response is not None


@pytest.mark.asyncio
async def test_all_keys_exhausted_raises_quickly():
    """Test that exhausting all keys raises quickly without long delays."""
    # All models fail with 429
    models = [
        MockModel("model-key1", fail_count=999),
        MockModel("model-key2", fail_count=999),
    ]

    rotating_model = RotatingFallbackModel(models)

    start_time = time.monotonic()
    with pytest.raises(ModelHTTPError) as exc_info:
        await rotating_model.request(
            messages=[],
            model_settings=None,
            model_request_parameters=MagicMock(),
        )
    elapsed_time = time.monotonic() - start_time

    # Should raise 429 error
    assert exc_info.value.status_code == 429

    # Should exhaust quickly (under 2 seconds for full rotation cycle)
    assert elapsed_time < 2.0, f"Exhaustion took {elapsed_time:.2f}s, expected < 2s"
