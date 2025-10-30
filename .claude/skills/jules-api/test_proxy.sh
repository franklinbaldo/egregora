#!/bin/bash
# Test script for Jules API Proxy with ngrok
# Run this on a machine WITHOUT 403 restrictions

set -e

echo "════════════════════════════════════════════════════════"
echo "Jules API Proxy + ngrok Test"
echo "════════════════════════════════════════════════════════"
echo ""

# Check requirements
echo "📋 Checking requirements..."

if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok not found. Install from: https://ngrok.com/download"
    exit 1
fi
echo "  ✓ ngrok installed"

if ! command -v uvx &> /dev/null; then
    echo "❌ uvx not found. Install with: pip install uv"
    exit 1
fi
echo "  ✓ uvx installed"

# Check API key
if [ -z "$JULES_API_KEY" ]; then
    echo ""
    echo "❌ JULES_API_KEY not set!"
    echo ""
    echo "Please set your Jules API key:"
    echo "  export JULES_API_KEY='your-api-key-here'"
    echo ""
    echo "Get your API key from: https://jules.google.com/settings#api"
    exit 1
fi
echo "  ✓ JULES_API_KEY is set"

echo ""
echo "🚀 Starting proxy server on port 5000..."
echo ""

# Start proxy server in background using uvx
uvx --from flask --from requests python3 "$(dirname "$0")/proxy_server.py" &
PROXY_PID=$!

# Wait for proxy to start
sleep 3

# Check if proxy is running
if ! kill -0 $PROXY_PID 2>/dev/null; then
    echo "❌ Proxy server failed to start"
    exit 1
fi

echo "  ✓ Proxy server started (PID: $PROXY_PID)"

# Test proxy locally
echo ""
echo "🧪 Testing proxy locally..."
HEALTH_CHECK=$(curl -s http://localhost:5000/health)
if echo "$HEALTH_CHECK" | grep -q "ok"; then
    echo "  ✓ Proxy health check passed"
else
    echo "  ❌ Proxy health check failed"
    kill $PROXY_PID
    exit 1
fi

echo ""
echo "🌐 Starting ngrok tunnel..."
echo ""
echo "NOTE: ngrok will display the tunnel URL. Keep this terminal open!"
echo "      In another terminal, test with:"
echo ""
echo "  export JULES_BASE_URL='https://your-ngrok-url/v1alpha'"
echo "  python jules_client.py list"
echo ""
echo "Press Ctrl+C to stop both proxy and ngrok"
echo ""

# Start ngrok (this will run in foreground)
ngrok http 5000

# Cleanup on exit
trap "kill $PROXY_PID 2>/dev/null" EXIT
