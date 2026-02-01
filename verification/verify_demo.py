import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

from playwright.sync_api import sync_playwright

PORT = 8003
SITE_DIR = "demo/.egregora/site"


def start_server() -> None:
    # Use partial to pass directory argument
    handler = partial(SimpleHTTPRequestHandler, directory=SITE_DIR)
    with TCPServer(("", PORT), handler) as httpd:
        httpd.serve_forever()


def verify() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://localhost:{PORT}/")

        page.screenshot(path="verification/homepage.png")

        page.goto(f"http://localhost:{PORT}/about/")
        page.screenshot(path="verification/about.png")

        browser.close()


if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(2)
    verify()
