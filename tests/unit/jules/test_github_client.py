import os
import sys
import pytest
import respx
import httpx
from pathlib import Path
from unittest import mock

# Add .jules to path so we can import jules.github
REPO_ROOT = Path(__file__).parents[3]
JULES_PATH = REPO_ROOT / ".jules"
if str(JULES_PATH) not in sys.path:
    sys.path.append(str(JULES_PATH))

from jules.github import GitHubClient, get_open_prs, get_base_sha

@pytest.fixture
def mock_env_token():
    with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
        yield

@pytest.fixture
def client(mock_env_token):
    return GitHubClient()

def test_client_init(mock_env_token):
    client = GitHubClient()
    assert client.token == "test-token"
    assert client.headers["Authorization"] == "Bearer test-token"
    assert client.headers["Accept"] == "application/vnd.github.v3+json"
    assert client.headers["User-Agent"] == "Jules-Bot"

def test_client_init_no_token():
    with mock.patch.dict(os.environ, {}, clear=True):
        client = GitHubClient()
        assert client.token is None
        assert "Authorization" not in client.headers

@respx.mock
def test_client_get_success(client):
    url = "https://api.github.com/test"
    respx.get(url).respond(json={"key": "value"})
    
    response = client._get("test")
    assert response == {"key": "value"}

@respx.mock
def test_client_get_failure(client):
    url = "https://api.github.com/test"
    respx.get(url).respond(status_code=404)
    
    response = client._get("test")
    assert response is None

@respx.mock
def test_get_open_prs(mock_env_token):
    owner = "owner"
    repo = "repo"
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params = {"state": "open", "per_page": "50", "sort": "updated", "direction": "desc"}
    
    mock_response = [
        {
            "number": 1,
            "title": "Test PR",
            "head": {"ref": "feature/branch"},
            "base": {"ref": "main"},
            "html_url": "http://github.com/owner/repo/pull/1",
            "user": {"login": "author"},
            "draft": False
        }
    ]
    
    # Matching strict params in respx 0.22+ usually involves passing params to route or using % syntax in url
    # For simplicity, let's just match the path and rely on the fact that our code sends params.
    # If we want to verify params, we can inspect the call.
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
    assert last_request.url.params["per_page"] == "50"

@respx.mock
def test_get_base_sha(mock_env_token):
    with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "owner", "GITHUB_REPOSITORY": "owner/repo"}):
        url = "https://api.github.com/repos/owner/repo/branches/main"
        respx.get(url).respond(json={"commit": {"sha": "abcdef123456"}})
        
        sha = get_base_sha("main")
        assert sha == "abcdef123456"

@respx.mock
def test_get_base_sha_failure(mock_env_token):
    with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "owner", "GITHUB_REPOSITORY": "owner/repo"}):
        url = "https://api.github.com/repos/owner/repo/branches/main"
        respx.get(url).respond(status_code=404)
        
        sha = get_base_sha("main")
        assert sha == "Unknown"
