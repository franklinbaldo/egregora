import http.server
import socketserver
import threading
import time
from playwright.sync_api import sync_playwright, expect
import os

PORT = 9000
DIRECTORY = "verification_site"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def start_server():
    # Allow address reuse to prevent "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at port {PORT}")
        httpd.serve_forever()

def verify_frontend():
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1)  # Give server time to start

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(f"http://localhost:{PORT}/test_post.html")

            # Expect the related posts container to be loaded
            # The .loaded class is added by JS when successful
            expect(page.locator("#related-posts-container")).to_have_class("related-posts loaded", timeout=5000)

            # Check for "Related Post" title
            expect(page.get_by_text("Related Post")).to_be_visible()

            # Check for score (should be 100%)
            expect(page.get_by_text("100% match")).to_be_visible()

            # Screenshot
            screenshot_path = os.path.abspath("verification_site/verification.png")
            page.screenshot(path=screenshot_path)
            print(f"Verification successful, screenshot saved at {screenshot_path}")
        except Exception as e:
            print(f"Verification failed: {e}")
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    verify_frontend()
