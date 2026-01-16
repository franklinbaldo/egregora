from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.exceptions import ModelHTTPError

from egregora.agents.writer import _execute_writer_with_error_handling


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.models.writer = "google-gla:gemini-1.5-flash"
    config.enrichment.model_rotation_enabled = True
    return config


@pytest.fixture
def mock_deps():
    deps = MagicMock()
    deps.window_label = "test_window"
    return deps


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1", "key2"])
@patch("egregora.agents.writer._get_openrouter_free_models", return_value=[])
def test_writer_rotates_keys_on_failure(
    mock_free_models, mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.side_effect = [
        ModelHTTPError(status_code=429, model_name="test-model", body={"message": "Rate limit exceeded"}),
        ("posts", "profiles"),
    ]

    posts, profiles = _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 2
    assert posts == "posts"
    assert profiles == "profiles"
    # Verify that the second call was made with the next key
    assert mock_write_posts.call_args_list[0][1]["api_key_override"] == "key1"
    assert mock_write_posts.call_args_list[1][1]["api_key_override"] == "key2"


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1"])
@patch(
    "egregora.agents.writer._iter_writer_models",
    return_value=["google-gla:gemini-1.5-flash", "google-gla:gemini-1.0-pro"],
)
def test_writer_rotates_models_on_persistent_failure(
    mock_iter_models, mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.side_effect = [
        ModelHTTPError(status_code=500, model_name="test-model", body={"message": "Internal Server Error"}),
        ("posts", "profiles"),
    ]

    posts, profiles = _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 2
    assert posts == "posts"
    assert profiles == "profiles"
    # Verify model overrides
    calls = mock_config.models.model_copy.call_args_list
    assert len(calls) >= 2
    assert calls[0].kwargs["update"]["writer"] == "google-gla:gemini-1.5-flash"
    assert calls[1].kwargs["update"]["writer"] == "google-gla:gemini-1.0-pro"


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1", "key2"])
@patch("egregora.agents.writer._iter_writer_models", return_value=["google-gla:gemini-1.5-flash"])
def test_writer_exhausts_all_retries_and_fails(
    mock_iter_models, mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.side_effect = ModelHTTPError(status_code=500, model_name="test-model", body={"message": "Internal Server Error"})

    with pytest.raises(RuntimeError, match="Writer agent exhausted ALL models and keys"):
        _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 2


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1"])
@patch("egregora.agents.writer._iter_writer_models", return_value=["google-gla:gemini-1.5-flash"])
def test_writer_succeeds_on_first_try(
    mock_iter_models, mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.return_value = ("posts", "profiles")

    posts, profiles = _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 1
    assert posts == "posts"
    assert profiles == "profiles"
    assert mock_write_posts.call_args_list[0][1]["api_key_override"] == "key1"
    # Verify config update logic
    call_args = mock_config.models.model_copy.call_args
    assert call_args.kwargs["update"]["writer"] == "google-gla:gemini-1.5-flash"
    
    new_models = mock_config.models.model_copy.return_value
    mock_config.model_copy.assert_called_with(deep=True, update={"models": new_models})
