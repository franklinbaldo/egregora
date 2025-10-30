# Testing the Jules API 403 Bypass

This guide helps you test the ngrok + proxy solution to bypass 403 errors.

## What You Need

1. **Jules API Key** - Get from https://jules.google.com/settings#api
2. **A machine WITHOUT 403 restrictions** (e.g., your laptop, not the restricted server)
3. **ngrok** - Free account at https://ngrok.com
4. **Python with uvx** - Install: `pip install uv`

## Quick Test (5 minutes)

### Step 1: Setup on Unrestricted Machine

On a machine that **can** access Google APIs (e.g., your laptop):

```bash
# 1. Clone the repo
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# 2. Set your Jules API key
export JULES_API_KEY="your-api-key-here"

# 3. Run the test script
./.claude/skills/jules-api/test_proxy.sh
```

This will:
- ✅ Start the Flask proxy server on port 5000
- ✅ Start ngrok tunnel
- ✅ Display your public URL (e.g., `https://abc123.ngrok.io`)

### Step 2: Use from Restricted Environment

On your **restricted server** (the one with 403 errors):

```bash
# Use the ngrok URL from Step 1
export JULES_BASE_URL="https://abc123.ngrok.io/v1alpha"
export JULES_API_KEY="dummy"  # Not needed, key is in proxy

# Test it!
cd egregora
python .claude/skills/jules-api/jules_client.py list
```

If it works, you've successfully bypassed the 403! 🎉

## Manual Testing (Step by Step)

If the script doesn't work, try manually:

### Terminal 1: Start Proxy Server

```bash
export JULES_API_KEY="your-api-key"
uvx --from flask --from requests python3 .claude/skills/jules-api/proxy_server.py
```

You should see:
```
🚀 Starting Jules API Proxy on http://0.0.0.0:5000
   Target: https://jules.googleapis.com/v1alpha
```

### Terminal 2: Test Proxy Locally

```bash
# Health check
curl http://localhost:5000/health

# Should return: {"status": "ok", "message": "Jules API Proxy is running"}

# Test Jules API through proxy
curl http://localhost:5000/v1alpha/sessions -H "Content-Type: application/json"

# Should return your sessions (or empty list if none exist)
```

### Terminal 3: Start ngrok

```bash
ngrok http 5000
```

Look for the "Forwarding" line:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:5000
```

Copy that `https://abc123.ngrok.io` URL.

### Terminal 4: Test from Anywhere

```bash
# Test the public URL
curl https://abc123.ngrok.io/health

# Test Jules API through public URL
export JULES_BASE_URL="https://abc123.ngrok.io/v1alpha"
python .claude/skills/jules-api/jules_client.py list
```

## Production Setup

For long-term use, ngrok might not be ideal (free tier has limits). Consider:

### Option A: ngrok Paid Plan
- Persistent URLs
- No session limits
- Better performance

```bash
# With persistent domain
ngrok http 5000 --domain=your-static-subdomain.ngrok.io
```

### Option B: Cloudflare Tunnel (Free!)

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

# Start tunnel
cloudflared tunnel --url http://localhost:5000
```

### Option C: Deploy Proxy to VPS

Deploy `proxy_server.py` to a VPS (DigitalOcean, Linode, etc.):

```bash
# On VPS
export JULES_API_KEY="your-key"
uvx --from flask --from requests python3 proxy_server.py

# Optionally: Use nginx as reverse proxy with HTTPS
```

## Troubleshooting

### "Connection refused" on localhost:5000

Proxy server isn't running. Check:
```bash
ps aux | grep proxy_server
```

### ngrok "Account limit exceeded"

Free ngrok accounts have limits. Either:
1. Wait an hour and try again
2. Sign up for paid plan
3. Use Cloudflare Tunnel instead

### Still getting 403 through proxy

This means the proxy server itself is in a restricted environment. Move it to:
- Your laptop
- A VPS
- Cloud function (AWS Lambda, etc.)

### "Module not found: flask"

Use `uvx` instead of direct Python:
```bash
uvx --from flask --from requests python3 proxy_server.py
```

## Security Notes

⚠️ **Important**: The proxy has access to your Jules API key!

- Don't run it on untrusted machines
- Don't share your ngrok URL publicly
- Consider adding `PROXY_AUTH_TOKEN` for extra security:

```bash
export PROXY_AUTH_TOKEN="some-secret-token"
uvx --from flask --from requests python3 proxy_server.py

# Clients must send the token
curl -H "X-Proxy-Auth: some-secret-token" https://your-ngrok.ngrok.io/health
```

## What This Does

```
[Restricted Server]
      ↓ (can't reach Google directly - 403)
      ↓
[ngrok URL: https://abc123.ngrok.io]
      ↓
[ngrok Service]
      ↓
[Your Laptop: localhost:5000]
      ↓ (proxy_server.py adds API key)
      ↓
[Google Jules API]
      ↓
[Response comes back through the tunnel]
```

Your restricted server talks to ngrok, which tunnels to your laptop, which talks to Google. Google sees the request coming from your laptop's IP (which isn't restricted), not from the restricted server.

## Questions?

- ngrok docs: https://ngrok.com/docs
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- Jules API: https://developers.google.com/jules/api
