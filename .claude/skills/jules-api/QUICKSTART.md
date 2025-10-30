# Jules API - Quick Start for 403 Bypass

## The Problem
You're getting 403 errors from Google Jules API even with a valid API key. This is likely due to IP/network restrictions in your environment.

## ⚡ Simplest Solution

**Before reading this guide**, try the SSH tunnel method (30 seconds):
```bash
ssh -D 8080 -N user@unrestricted-machine &
export HTTPS_PROXY="socks5://localhost:8080"
python jules_client.py list
```

See **SIMPLE_BYPASS.md** for details.

---

## The ngrok Solution

If you don't have SSH access, use **ngrok** to tunnel requests through an unrestricted machine.

## What You Need

**Required:**
- 🔑 Jules API Key (get from https://jules.google.com/settings#api)
- 💻 A machine without 403 errors (e.g., your laptop)
- 🌐 ngrok account (free at https://ngrok.com)
- 🐍 Python with uvx (`pip install uv`)

**Time to setup:** ~5 minutes

---

## 🚀 Quick Setup (3 commands)

On your **unrestricted machine** (laptop):

```bash
# 1. Set your Jules API key
export JULES_API_KEY="your-api-key-here"

# 2. Clone and navigate to repo
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# 3. Run the test script
./.claude/skills/jules-api/test_proxy.sh
```

The script will:
1. ✅ Check all requirements
2. ✅ Start proxy server on port 5000
3. ✅ Start ngrok tunnel
4. ✅ Display your public URL (e.g., `https://abc123.ngrok.io`)

**Keep this terminal open!**

---

## 📱 Use from Restricted Server

On your **restricted server** (the one with 403 errors):

```bash
# Set the ngrok URL from above
export JULES_BASE_URL="https://abc123.ngrok.io/v1alpha"

# Test it!
python .claude/skills/jules-api/jules_client.py list
```

**Success!** If this works, you've bypassed the 403 restriction! 🎉

---

## 📖 Full Documentation

- **TESTING.md** - Complete testing guide with manual steps
- **bypass_403.md** - 6 different bypass solutions explained
- **proxy_server.py** - The proxy server code
- **README.md** - Jules skill documentation

---

## ❓ Need Help?

### I don't have an unrestricted machine
Use a VPS (DigitalOcean, Linode) or cloud function (AWS Lambda, Cloudflare Workers).
See `bypass_403.md` for cloud-based solutions.

### ngrok session expired
Free tier has time limits. Options:
1. Restart the script (new URL each time)
2. Upgrade to ngrok paid plan (persistent URLs)
3. Use Cloudflare Tunnel (free alternative)

### Still getting 403
The proxy server itself might be in a restricted environment. Move it to:
- Your home computer
- A VPS
- A cloud service

---

## 🏃 I Want to Skip Testing

If you just want to understand the solution without testing:

**Read:** `bypass_403.md` - Explains all 6 bypass methods
**Best for production:** Cloudflare Workers (free, reliable, no infrastructure)
**Best for testing:** ngrok (this guide)

---

## 🔒 Security Note

The proxy server has access to your API key. Only run it on machines you trust, and don't share your ngrok URL publicly.

For extra security, set a proxy auth token:
```bash
export PROXY_AUTH_TOKEN="your-secret-token"
```

---

## Next Steps

1. **For development:** Keep using ngrok (restart as needed)
2. **For production:** Deploy to Cloudflare Workers or VPS
3. **Document your setup:** Update `CLAUDE.md` with your chosen solution

Happy coding! 🚀
