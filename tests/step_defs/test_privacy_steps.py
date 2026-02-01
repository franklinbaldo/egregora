import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect
from pytest_bdd import given, scenario, then, when


@scenario("../features/privacy.feature", "Verify no external requests on demo site")
def test_privacy_compliance():
    """Verify privacy compliance."""


@pytest.fixture(scope="module")
def demo_site():
    """Generates and builds the demo site."""
    # Clean previous
    shutil.rmtree("demo", ignore_errors=True)

    # Generate
    # We use 'uv run egregora demo'
    # Assuming we are at repo root
    subprocess.run(["uv", "run", "egregora", "demo"], check=True)

    # Build
    # We need to run mkdocs build inside the demo directory
    # Note: egregora demo places mkdocs.yml in .egregora/mkdocs.yml
    subprocess.run(["uv", "run", "mkdocs", "build", "-f", ".egregora/mkdocs.yml"], cwd="demo", check=True)

    site_dir = Path("demo/.egregora/site").resolve()
    if not site_dir.exists():
        msg = f"Site directory not found at {site_dir}"
        raise RuntimeError(msg)

    yield site_dir
    # Cleanup optional
    # shutil.rmtree("demo", ignore_errors=True)


@pytest.fixture(scope="module")
def site_server(demo_site):
    """Starts a python http server serving the demo site."""
    port = 8087  # Use a different port than original test to avoid conflict if run in parallel
    process = subprocess.Popen(
        ["python", "-m", "http.server", str(port)],
        cwd=demo_site,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server
    import requests

    for _ in range(20):
        try:
            requests.get(f"http://localhost:{port}", timeout=1)
            break
        except requests.ConnectionError:
            time.sleep(0.5)
    else:
        process.terminate()
        stdout, stderr = process.communicate()
        msg = f"Server failed to start at port {port}:\nStdout: {stdout}\nStderr: {stderr}"
        raise RuntimeError(msg)

    yield f"http://localhost:{port}"

    process.terminate()
    process.wait()


@pytest.fixture
def context_requests():
    return []


@given("a clean demo site is generated")
def clean_demo_site(demo_site):
    """Ensure site is generated."""
    assert demo_site.exists()


@when("I navigate to the home page")
def navigate_home(page: Page, site_server, context_requests):
    """Navigate to home page and record requests."""

    def handle_request(request):
        context_requests.append(request.url)

    page.on("request", handle_request)

    page.goto(site_server)
    page.wait_for_load_state("networkidle")


@then("no requests should be made to external domains")
def verify_no_external_requests(context_requests):
    """Check recorded requests for violations."""
    external_domains = [
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "unpkg.com",
        "cdn.jsdelivr.net",
    ]
    violations = []
    for url in context_requests:
        parsed = urlparse(url)
        if any(domain in parsed.netloc for domain in external_domains):
            violations.append(url)

    assert not violations, f"Found external requests: {violations}"


@then('the "Outfit" font should be loaded locally')
def verify_outfit_local(page: Page):
    """Verify Outfit font usage."""
    header = page.locator("h1").first
    expect(header).to_have_css("font-family", re.compile(r"Outfit"))


@then('the "Inter" font should be loaded locally')
def verify_inter_local(page: Page):
    """Verify Inter font usage."""
    body = page.locator("body")
    expect(body).to_have_css("font-family", re.compile(r"Inter"))
