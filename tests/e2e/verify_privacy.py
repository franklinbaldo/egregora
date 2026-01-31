
import sys
import os
import time
import subprocess
import threading
from playwright.sync_api import sync_playwright

def verify_privacy():
    """Verify no external requests are made."""
    print("Verifying privacy compliance...")

    site_dir = "demo/.egregora/site"
    # Check if site exists
    if not os.path.exists(site_dir):
        print(f"Error: {site_dir} does not exist. Run 'egregora demo' and 'mkdocs build' first.")
        sys.exit(1)

    # Start server in background
    # We can't easily kill the thread/process in this simple script, but for a one-off run in a container it's fine.
    # Better: use subprocess.Popen
    server_process = subprocess.Popen([sys.executable, "-m", "http.server", "8001", "--directory", site_dir], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    time.sleep(2) # Wait for server

    external_requests = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Intercept requests
            page.on("request", lambda request: external_requests.append(request.url) if "localhost" not in request.url and "127.0.0.1" not in request.url else None)

            page.goto("http://localhost:8001")
            time.sleep(2) # Wait for network idle

            browser.close()
    finally:
        server_process.kill()

    # Analyze
    violations = [url for url in external_requests if not url.startswith("data:")]

    if violations:
        print("❌ Privacy Violations Found (External Requests):")
        for url in violations:
            print(f"  - {url}")
        sys.exit(1)
    else:
        print("✅ No external requests found. Privacy compliant.")
        sys.exit(0)

if __name__ == "__main__":
    verify_privacy()
