import os
import re
import shutil
import subprocess
import time

import pytest
import requests
from playwright.sync_api import Page, expect


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

    site_dir = os.path.abspath("demo/.egregora/site")
    if not os.path.exists(site_dir):
        msg = f"Site directory not found at {site_dir}"
        raise RuntimeError(msg)

    yield site_dir


@pytest.fixture(scope="module")
def site_server(demo_site):
    """Starts a python http server serving the demo site."""
    port = 8086
    process = subprocess.Popen(
        ["python", "-m", "http.server", str(port)],
        cwd=demo_site,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server
    for _ in range(20):
        try:
            requests.get(f"http://localhost:{port}")
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


def test_privacy_assets(page: Page, site_server):
    """Verifies no external requests are made and local fonts are loaded."""

    external_domains = [
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "unpkg.com",
        "cdn.jsdelivr.net",
    ]

    requests_made = []

    def handle_request(request):
        requests_made.append(request.url)

    page.on("request", handle_request)

    page.goto(site_server)

    # Wait for network idle to ensure assets are requested
    page.wait_for_load_state("networkidle")

    # Check for external requests
    # We check if the request starts with the forbidden domains
    # Or strict check of the host
    from urllib.parse import urlparse

    violations = []
    for url in requests_made:
        parsed = urlparse(url)
        if any(domain in parsed.netloc for domain in external_domains):
            violations.append(url)

    assert not violations, f"Found external requests: {violations}"

    # Check if Outfit was requested (it should be local)
    outfit_requests = [url for url in requests_made if "outfit.woff2" in url]

    # Note: We rely on the font actually being used on the home page.
    # The home page has H1, which uses Outfit.

    # If checking requests is flaky (due to caching), we can also check computed styles.
    # But a fresh browser context should request it.

    # For debugging: print all requests
    # print("Requests made:", requests_made)

    if not outfit_requests:
        # Fallback verification: Check computed style
        header = page.locator("h1").first
        # The CSS says: font-family: 'Outfit', sans-serif !important;
        # Computed style should start with Outfit or "Outfit"
        expect(header).to_have_css("font-family", re.compile(r"Outfit"))

    # Also verify Inter is used for body
    body = page.locator("body")
    expect(body).to_have_css("font-family", re.compile(r"Inter"))

    # Take screenshot for visual verification
    page.screenshot(path="privacy_verification.png")
