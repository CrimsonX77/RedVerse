# Quick Reference - RedVerse Tools MCP Authentication

## TL;DR

**SSE mode now requires authentication. Set `REDVERSE_MCP_API_KEY` before starting.**

## Quick Setup (3 steps)

```bash
# 1. Generate API key
export REDVERSE_MCP_API_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')

# 2. Start server
python redverse_tools_mcp.py --transport sse

# 3. Connect with authentication
curl -H "X-API-Key: $REDVERSE_MCP_API_KEY" http://localhost:8942/tools/list_launcher_tools
```

## Transport Modes

| Mode | Network | Auth Required | Use Case |
|------|---------|---------------|----------|
| `stdio` (default) | No | No | Local AI clients (Claude Desktop, Ollama) |
| `sse` | Yes | **YES** | Remote access, dashboards, web clients |

## Common Commands

### Start in stdio mode (local, no auth)
```bash
python redverse_tools_mcp.py
```

### Start in SSE mode (network, requires auth)
```bash
export REDVERSE_MCP_API_KEY='your-secret-key'
python redverse_tools_mcp.py --transport sse --host 0.0.0.0 --port 8942
```

### Generate secure API key
```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Test authentication
```bash
bash test_mcp_auth.sh
```

## Client Examples

### cURL
```bash
curl -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{"tool": "list_launcher_tools", "params": {}}' \
     http://localhost:8942/tools
```

### Python
```python
import requests

headers = {
    'X-API-Key': 'your-api-key-here',
    'Content-Type': 'application/json'
}

response = requests.post(
    'http://localhost:8942/tools/list_launcher_tools',
    headers=headers,
    json={'params': {}}
)
print(response.json())
```

### JavaScript
```javascript
fetch('http://localhost:8942/tools/list_launcher_tools', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your-api-key-here',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({params: {}})
})
.then(r => r.json())
.then(data => console.log(data));
```

## Troubleshooting

### Error: "SECURITY ERROR: SSE transport requires authentication"
**Solution:** Set the API key environment variable before starting:
```bash
export REDVERSE_MCP_API_KEY='your-key-here'
```

### Error: "Authentication required. Provide valid API key"
**Solution:** Include the API key in your request headers:
```bash
curl -H "X-API-Key: your-key" http://localhost:8942/...
```

### Error: API key not working
**Check:**
1. Environment variable is set: `echo $REDVERSE_MCP_API_KEY`
2. Header name is correct: `X-API-Key` or `Authorization: Bearer`
3. Key matches exactly (no extra spaces or quotes)

## Security Checklist

- [ ] Generated strong random API key (32+ bytes)
- [ ] Set `REDVERSE_MCP_API_KEY` environment variable
- [ ] Never committed API key to git
- [ ] Using HTTPS in production (reverse proxy)
- [ ] Restricted network access (firewall rules)
- [ ] Monitoring authentication failures
- [ ] Have key rotation plan

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDVERSE_MCP_API_KEY` | **Yes** (SSE mode) | None | API key for authentication |
| `REDVERSE_LAUNCHERS_DIR` | No | `./launchers` | Directory containing launcher scripts |
| `REDVERSE_TOOL_TIMEOUT` | No | `30` | Tool execution timeout (seconds) |

## Production Deployment

### Recommended Setup
```bash
# 1. Generate and store key securely
python -c 'import secrets; print(secrets.token_urlsafe(32))' > /secure/path/mcp_key.txt
chmod 600 /secure/path/mcp_key.txt

# 2. Load key from secure storage
export REDVERSE_MCP_API_KEY=$(cat /secure/path/mcp_key.txt)

# 3. Start with restricted binding
python redverse_tools_mcp.py --transport sse --host 127.0.0.1 --port 8942

# 4. Use reverse proxy (nginx/caddy) for HTTPS
```

### Nginx Reverse Proxy Example
```nginx
server {
    listen 443 ssl http2;
    server_name mcp.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8942;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Support

- **Documentation:** See `SECURITY_MCP.md` for detailed security information
- **Testing:** Run `bash test_mcp_auth.sh` to verify authentication
- **Summary:** See `SECURITY_PATCH_SUMMARY.md` for patch details

## Migration from Unauthenticated Version

If upgrading from a version without authentication:

1. **Generate API key** (see Quick Setup above)
2. **Update server startup** to include `REDVERSE_MCP_API_KEY`
3. **Update all clients** to send API key in headers
4. **Test thoroughly** before production deployment
5. **Monitor logs** for authentication errors

**Note:** stdio mode is unchanged and requires no migration.
