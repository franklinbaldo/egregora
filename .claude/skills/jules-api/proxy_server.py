#!/usr/bin/env python3
"""
Simple HTTP proxy server for Jules API to bypass network restrictions.

Usage:
    1. Run on a machine WITHOUT 403 restrictions:
       export JULES_API_KEY="your-api-key"
       python proxy_server.py

    2. Expose via ngrok (or similar):
       ngrok http 5000

    3. Use from restricted environment:
       export JULES_BASE_URL="https://your-ngrok-url/v1alpha"
       python jules_client.py list
"""

import os
import sys
from flask import Flask, request, Response
import requests

app = Flask(__name__)

JULES_BASE_URL = "https://jules.googleapis.com/v1alpha"
JULES_API_KEY = os.environ.get("JULES_API_KEY")

# Optional: Add authentication to your proxy
PROXY_AUTH_TOKEN = os.environ.get("PROXY_AUTH_TOKEN")


@app.route("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "message": "Jules API Proxy is running"}


@app.route("/v1alpha/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy_v1alpha(path):
    """Proxy requests to Jules API v1alpha."""
    return proxy(f"v1alpha/{path}")


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(path):
    """
    Proxy all requests to Jules API.

    The API key can be provided in two ways:
    1. In the proxy server environment (JULES_API_KEY) - recommended
    2. In the request header (X-Goog-Api-Key) - less secure for public proxies
    """
    # Optional: Check proxy authentication
    if PROXY_AUTH_TOKEN:
        auth_header = request.headers.get("X-Proxy-Auth")
        if auth_header != PROXY_AUTH_TOKEN:
            return Response(
                '{"error": "Unauthorized"}',
                status=401,
                mimetype="application/json"
            )

    # Build target URL
    url = f"{JULES_BASE_URL}/{path}"

    # Prepare headers
    headers = {"Content-Type": "application/json"}

    # Use API key from server environment (preferred) or from request
    api_key = JULES_API_KEY or request.headers.get("X-Goog-Api-Key")
    if not api_key:
        return Response(
            '{"error": "No API key provided"}',
            status=400,
            mimetype="application/json"
        )

    headers["X-Goog-Api-Key"] = api_key

    try:
        # Forward request to Jules API
        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            json=request.get_json() if request.is_json else None,
            params=request.args,
            timeout=30,
        )

        # Return response
        return Response(
            resp.content,
            status=resp.status_code,
            headers=dict(resp.headers)
        )

    except requests.exceptions.RequestException as e:
        return Response(
            f'{{"error": "Proxy error: {str(e)}"}}',
            status=502,
            mimetype="application/json"
        )


if __name__ == "__main__":
    if not JULES_API_KEY:
        print("=" * 60)
        print("WARNING: JULES_API_KEY not set!")
        print("=" * 60)
        print("\nThe proxy will forward API keys from client requests,")
        print("which is less secure for public proxies.")
        print("\nRecommended: Set JULES_API_KEY in the proxy environment:")
        print("  export JULES_API_KEY='your-api-key-here'")
        print("=" * 60)
        print()

    if PROXY_AUTH_TOKEN:
        print("✓ Proxy authentication enabled")
        print(f"  Clients must send: X-Proxy-Auth: {PROXY_AUTH_TOKEN}")
    else:
        print("⚠ Proxy authentication disabled (set PROXY_AUTH_TOKEN to enable)")

    print(f"\n🚀 Starting Jules API Proxy on http://0.0.0.0:5000")
    print(f"   Target: {JULES_BASE_URL}")
    print(f"   Health check: http://localhost:5000/health\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
