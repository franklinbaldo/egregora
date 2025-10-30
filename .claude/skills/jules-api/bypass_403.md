# Bypassing 403 Errors with Jules API

If you're getting 403 errors from Google even with a valid API key, this is likely due to network restrictions or IP-based blocking. Here are several solutions:

## Solution 1: HTTP Proxy (Simplest)

Use a simple HTTP/SOCKS proxy to route requests through a different IP:

```python
import os
import requests

# Configure proxy
proxies = {
    'http': 'http://proxy-server:port',
    'https': 'http://proxy-server:port',
}

# Use in jules_client.py
response = requests.post(url, headers=headers, json=data, proxies=proxies)
```

### Free proxy services:
- ProxyMesh (has free tier)
- Hide.me
- ProxyScrape

## Solution 2: VPN

Run your entire environment through a VPN:

```bash
# Example with WireGuard
sudo wg-quick up wg0

# Or OpenVPN
sudo openvpn --config your-config.ovpn
```

## Solution 3: Cloudflare Workers (Recommended)

Deploy a simple proxy as a Cloudflare Worker (free tier available):

```javascript
// worker.js
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const apiKey = request.headers.get('X-Jules-Api-Key')

  // Proxy to Jules API
  const julesUrl = 'https://jules.googleapis.com' + url.pathname

  const response = await fetch(julesUrl, {
    method: request.method,
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': apiKey,
    },
    body: request.body
  })

  return new Response(response.body, {
    status: response.status,
    headers: response.headers
  })
}
```

Then update `jules_client.py`:
```python
# In __init__
self.base_url = "https://your-worker.workers.dev/v1alpha"
```

## Solution 4: ngrok Tunnel

Create a local proxy server and expose it via ngrok:

### Step 1: Create proxy server

```python
# proxy_server.py
from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)
JULES_API_KEY = os.environ.get("JULES_API_KEY")

@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    url = f"https://jules.googleapis.com/v1alpha/{path}"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": JULES_API_KEY,
    }

    resp = requests.request(
        method=request.method,
        url=url,
        headers=headers,
        json=request.get_json() if request.is_json else None,
    )

    return Response(resp.content, status=resp.status_code)

if __name__ == "__main__":
    app.run(port=5000)
```

### Step 2: Run with ngrok

```bash
# Terminal 1: Run proxy server on a machine WITHOUT 403 issues
export JULES_API_KEY="your-key"
pip install flask requests
python proxy_server.py

# Terminal 2: Expose via ngrok
ngrok http 5000

# You'll get a URL like: https://abc123.ngrok.io
```

### Step 3: Use the tunnel

```bash
# In your restricted environment
export JULES_BASE_URL="https://abc123.ngrok.io/v1alpha"
export JULES_API_KEY="dummy"  # API key is in the proxy server

python jules_client.py list
```

## Solution 5: AWS Lambda Proxy

Deploy a serverless proxy on AWS Lambda (behind API Gateway):

```python
# lambda_function.py
import json
import urllib3
import os

http = urllib3.PoolManager()
JULES_API_KEY = os.environ['JULES_API_KEY']

def lambda_handler(event, context):
    path = event['path']
    method = event['httpMethod']
    body = event.get('body', '')

    url = f"https://jules.googleapis.com/v1alpha{path}"

    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': JULES_API_KEY
    }

    response = http.request(
        method,
        url,
        body=body,
        headers=headers
    )

    return {
        'statusCode': response.status,
        'body': response.data.decode('utf-8'),
        'headers': {'Content-Type': 'application/json'}
    }
```

## Solution 6: Docker with VPN

Run your client in a Docker container with VPN:

```dockerfile
# Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y openvpn
COPY vpn-config.ovpn /etc/openvpn/
COPY jules_client.py /app/

CMD openvpn --config /etc/openvpn/vpn-config.ovpn --daemon && \
    sleep 5 && \
    python /app/jules_client.py "$@"
```

## Recommended Solution

For your case, I recommend **Solution 3 (Cloudflare Workers)** because:
- ✅ Free tier available
- ✅ Reliable and fast
- ✅ No infrastructure to manage
- ✅ Scales automatically
- ✅ Simple to deploy

Alternatively, **Solution 4 (ngrok)** is good for quick testing if you have access to another machine that doesn't have the 403 issue.

## Testing Your Solution

```bash
# Test the proxy
curl -X GET "https://your-proxy-url/v1alpha/sessions" \
  -H "X-Jules-Api-Key: your-api-key"

# If successful, update jules_client.py
export JULES_BASE_URL="https://your-proxy-url/v1alpha"
python jules_client.py list
```
