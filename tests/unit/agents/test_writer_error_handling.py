from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.exceptions import ModelHTTPError

from egregora.agents.writer import _execute_writer_with_error_handling


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.models.writer = "google-gla:gemini-1.5-flash"
    config.enrichment.model_rotation_enabled = True
    # Configure the mock returned by model_copy to match the expected behavior
    # When config.model_copy() is called, it returns a new config instance.
    # We need to make sure that new instance behaves like a config too.
    new_config = MagicMock()
    config.model_copy.return_value = new_config
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
    _mock_free_models, _mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.side_effect = [
        ModelHTTPError(
            body={"message": "Rate limit exceeded"},
            status_code=429,
            model_name="google-gla:gemini-1.5-flash",
        ),
        ("posts", "profiles"),
    ]

    posts, profiles = _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 2
    assert posts == "posts"
    assert profiles == "profiles"
    assert mock_write_posts.call_args_list[0][1]["api_key_override"] == "key1"
    assert mock_write_posts.call_args_list[1][1]["api_key_override"] == "key2"


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1"])
@patch(
    "egregora.agents.writer._iter_writer_models",
    return_value=["google-gla:gemini-1.5-flash", "google-gla:gemini-1.0-pro"],
)
def test_writer_rotates_models_on_persistent_failure(
    _mock_iter_models, _mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.side_effect = [
        ModelHTTPError(
            body={"message": "Internal Server Error"},
            status_code=500,
            model_name="google-gla:gemini-1.5-flash",
        ),
        ("posts", "profiles"),
    ]

    posts, profiles = _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 2
    assert posts == "posts"
    assert profiles == "profiles"

    # Check that the config passed to write_posts_with_pydantic_agent was modified correctly
    # The first call should use the first model, the second call the second model.
    # However, since we are mocking config.model_copy(), we need to inspect the update arguments passed to it.

    # We can inspect the arguments passed to config.model_copy to see if the model was updated.
    assert mock_config.model_copy.call_count >= 2

    # First iteration
    # In the code: models_copy = config.models.model_copy(update={"writer": model})
    # config_copy = config.model_copy(update={"models": models_copy})
    # So we are looking for the 'models' update.

    # The passed config to the function is the result of config.model_copy().
    # Since we returned a single mock object `new_config` for all calls, we can't distinguish them easily by identity
    # unless we use side_effect to return different mocks.

    # But we can verify that the code *attempted* to set the correct model name.
    # The `models` object inside `update` is a copy of `config.models`.

    # Let's inspect call_args of `config.models.model_copy`.
    assert mock_config.models.model_copy.call_count >= 2

    # The argument to `config.models.model_copy` should contain the updated writer model.
    call1 = mock_config.models.model_copy.call_args_list[0]
    assert call1[1]["update"]["writer"] == "google-gla:gemini-1.5-flash"

    call2 = mock_config.models.model_copy.call_args_list[1]
    assert call2[1]["update"]["writer"] == "google-gla:gemini-1.0-pro"


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1", "key2"])
@patch("egregora.agents.writer._iter_writer_models", return_value=["google-gla:gemini-1.5-flash"])
def test_writer_exhausts_all_retries_and_fails(
    _mock_iter_models, _mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.side_effect = ModelHTTPError(
        body={"message": "Internal Server Error"},
        status_code=500,
        model_name="google-gla:gemini-1.5-flash",
    )

    with pytest.raises(RuntimeError, match="Writer agent exhausted ALL models and keys"):
        _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 2


@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
@patch("egregora.agents.writer.get_google_api_keys", return_value=["key1"])
@patch("egregora.agents.writer._iter_writer_models", return_value=["google-gla:gemini-1.5-flash"])
def test_writer_succeeds_on_first_try(
    _mock_iter_models, _mock_google_keys, mock_write_posts, mock_config, mock_deps
):
    mock_write_posts.return_value = ("posts", "profiles")

    posts, profiles = _execute_writer_with_error_handling("prompt", mock_config, mock_deps)

    assert mock_write_posts.call_count == 1
    assert posts == "posts"
    assert profiles == "profiles"
    assert mock_write_posts.call_args_list[0][1]["api_key_override"] == "key1"

    # Verify the model used
    call_args = mock_config.models.model_copy.call_args
    assert call_args[1]["update"]["writer"] == "google-gla:gemini-1.5-flash"
