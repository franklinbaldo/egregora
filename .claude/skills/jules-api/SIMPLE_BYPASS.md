# Simple 403 Bypass Solutions

The Jules client now supports standard HTTP/SOCKS proxies! No custom proxy server needed.

## ✨ NEW: Just Set Environment Variable

The **simplest** way is to use a standard HTTP/SOCKS proxy:

```bash
# Option 1: HTTP proxy
export HTTPS_PROXY="http://your-proxy:port"
python jules_client.py list

# Option 2: SOCKS proxy (requires requests[socks])
export HTTPS_PROXY="socks5://your-proxy:port"
python jules_client.py list
```

That's it! The client automatically uses the proxy.

---

## Solution 1: SSH Tunnel (EASIEST - No ngrok needed!)

If you have SSH access to a machine without 403 restrictions:

### Setup (30 seconds)

```bash
# On your restricted server, create SOCKS proxy via SSH
ssh -D 8080 -N user@your-unrestricted-machine.com &

# Use it
export HTTPS_PROXY="socks5://localhost:8080"
python jules_client.py list
```

**Done!** No ngrok, no custom proxy server, just SSH.

### Why This is Best:
- ✅ No extra software to install
- ✅ No ngrok account needed
- ✅ Secure (uses SSH encryption)
- ✅ Works anywhere you have SSH access
- ✅ No API key on remote machine

---

## Solution 2: Use Any HTTP Proxy

If you have access to an HTTP proxy (company proxy, VPN, etc.):

```bash
export HTTPS_PROXY="http://proxy.company.com:8080"
export HTTP_PROXY="http://proxy.company.com:8080"

python jules_client.py list
```

---

## Solution 3: Cloudflare WARP (Free VPN)

Install Cloudflare WARP for a free VPN:

```bash
# Install (Ubuntu/Debian)
curl https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt update && sudo apt install cloudflare-warp

# Connect
warp-cli register
warp-cli connect

# Use Jules API (automatically routes through WARP)
python jules_client.py list
```

---

## Solution 4: ngrok (If you still want it)

If you prefer ngrok, see `QUICKSTART.md` for the full guide.

But honestly, **SSH tunnel is simpler** if you have SSH access anywhere.

---

## Comparison Table

| Method | Setup Time | Cost | Best For |
|--------|-----------|------|----------|
| **SSH Tunnel** | 30 sec | Free | Anyone with SSH access |
| HTTP Proxy | 10 sec | Varies | Corporate networks |
| Cloudflare WARP | 2 min | Free | Personal use |
| ngrok + custom proxy | 5 min | Free tier | Testing without SSH |

---

## Examples

### Example 1: SSH Tunnel to Your Laptop

```bash
# On restricted server
ssh -D 8080 -N username@my-laptop.local &
export HTTPS_PROXY="socks5://localhost:8080"
python jules_client.py list
```

### Example 2: SSH Tunnel to VPS

```bash
# On restricted server
ssh -D 8080 -N root@my-vps.com &
export HTTPS_PROXY="socks5://localhost:8080"
python jules_client.py list
```

### Example 3: Use in Python Code

```python
from jules_client import JulesClient

# Method 1: Via environment variable (set HTTPS_PROXY)
client = JulesClient()

# Method 2: Explicit proxy
client = JulesClient(
    proxies={
        "http": "socks5://localhost:8080",
        "https": "socks5://localhost:8080"
    }
)

# Use normally
sessions = client.list_sessions()
```

### Example 4: Persistent SSH Tunnel

Create a systemd service for persistent SSH tunnel:

```bash
# /etc/systemd/system/jules-tunnel.service
[Unit]
Description=SSH Tunnel for Jules API
After=network.target

[Service]
User=youruser
ExecStart=/usr/bin/ssh -D 8080 -N -o ServerAliveInterval=60 user@remote-host
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable jules-tunnel
sudo systemctl start jules-tunnel
export HTTPS_PROXY="socks5://localhost:8080"
```

---

## Troubleshooting

### "Connection refused" with SSH tunnel

Check if SSH tunnel is running:
```bash
ps aux | grep "ssh -D"
netstat -ln | grep 8080
```

### "SOCKS5 not supported"

Install SOCKS support:
```bash
pip install requests[socks]
# or
pip install pysocks
```

### SSH tunnel keeps disconnecting

Add keepalive options:
```bash
ssh -D 8080 -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3 user@host
```

---

## Which Solution Should I Use?

**Start here:**
1. ✅ Do you have SSH access to a non-restricted machine? → **SSH Tunnel**
2. ✅ Are you on a corporate network? → **Existing HTTP Proxy**
3. ✅ Need a quick personal VPN? → **Cloudflare WARP**
4. ✅ None of the above? → **ngrok** (see QUICKSTART.md)

**For production:**
- Deploy proxy on VPS
- Or use Cloudflare Workers (see bypass_403.md)

---

## Summary

You no longer need a custom proxy server! Just:

1. **Get access to any proxy** (SSH tunnel, HTTP proxy, VPN)
2. **Set HTTPS_PROXY** environment variable
3. **Use jules_client.py** normally

The client handles the rest automatically.
