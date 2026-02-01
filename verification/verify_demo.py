from playwright.sync_api import sync_playwright
import threading
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import time
import os
from functools import partial

PORT = 8003
SITE_DIR = "demo/.egregora/site"

def start_server():
    # Use partial to pass directory argument
    handler = partial(SimpleHTTPRequestHandler, directory=SITE_DIR)
    with TCPServer(("", PORT), handler) as httpd:
        httpd.serve_forever()

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://localhost:{PORT}/")

        print("Taking screenshot of homepage...")
        page.screenshot(path="verification/homepage.png")

        print("Taking screenshot of about page...")
        page.goto(f"http://localhost:{PORT}/about/")
        page.screenshot(path="verification/about.png")

        browser.close()

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(2)
    verify()
