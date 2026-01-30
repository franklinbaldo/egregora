import os
import sys
from pathlib import Path
from unittest import mock

import pytest
import respx

# Add .team to path so we can import repo.core.github
REPO_ROOT = Path(__file__).parents[3]
TEAM_PATH = REPO_ROOT / ".team"
if str(TEAM_PATH) not in sys.path:
    sys.path.append(str(TEAM_PATH))

from repo.core.github import GitHubClient, get_base_sha, get_open_prs  # noqa: E402


@pytest.fixture
def mock_env_token():
    """Fixture to mock GITHUB_TOKEN environment variable."""
    with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
        yield


@pytest.fixture
def client(mock_env_token):
    """Fixture for GitHubClient with a mock token."""
    _ = mock_env_token
    return GitHubClient()


@pytest.mark.usefixtures("mock_env_token")
def test_client_init():
    """Test client initialization with token."""
    client = GitHubClient()
    assert client.token == "test-token"  # noqa: S105
    assert client.headers["Authorization"] == "Bearer test-token"
    assert client.headers["Accept"] == "application/vnd.github.v3+json"
    assert client.headers["User-Agent"] == "Jules-Bot"


def test_client_init_no_token():
    """Test client initialization without token."""
    with mock.patch.dict(os.environ, {}, clear=True):
        client = GitHubClient()
        assert client.token is None
        assert "Authorization" not in client.headers


@respx.mock
def test_client_get_success(client):
    """Test successful GET request."""
    url = "https://api.github.com/test"
    respx.get(url).respond(json={"key": "value"})

    response = client._get("test")
    assert response == {"key": "value"}


@respx.mock
def test_client_get_failure(client):
    """Test failed GET request returns None."""
    url = "https://api.github.com/test"
    respx.get(url).respond(status_code=404)

    response = client._get("test")
    assert response is None


@respx.mock
def test_get_open_prs(mock_env_token):
    """Test fetching open PRs."""
    _ = mock_env_token
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"

    mock_response = [
        {
            "number": 1,
            "title": "Test PR",
            "body": "This is a test PR.",
            "head": {"ref": "feature/branch"},
            "base": {"ref": "main"},
            "html_url": "http://github.com/owner/repo/pull/1",
            "user": {"login": "author"},
            "draft": False,
        }
    ]

    route = respx.get(url).respond(json=mock_response)

    prs = get_open_prs(owner, repo)
    assert len(prs) == 1
    assert prs[0]["number"] == 1
    assert prs[0]["title"] == "Test PR"
    assert prs[0]["author"]["login"] == "author"

    # Verify params were sent
    assert route.called
    last_request = route.calls.last.request
    assert last_request.url.params["state"] == "open"
    assert last_request.url.params["per_page"] == "100"


@respx.mock
def test_get_base_sha(mock_env_token):
    """Test fetching base branch SHA."""
    _ = mock_env_token
    with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "owner", "GITHUB_REPOSITORY": "owner/repo"}):
        url = "https://api.github.com/repos/owner/repo/branches/main"
        respx.get(url).respond(json={"commit": {"sha": "abcdef123456"}})

        sha = get_base_sha("main")
        assert sha == "abcdef123456"


@respx.mock
def test_get_base_sha_failure(mock_env_token):
    """Test fallback when fetching SHA fails."""
    _ = mock_env_token
    with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "owner", "GITHUB_REPOSITORY": "owner/repo"}):
        url = "https://api.github.com/repos/owner/repo/branches/main"
        respx.get(url).respond(status_code=404)

        sha = get_base_sha("main")
        assert sha == "Unknown"
