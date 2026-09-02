# RedVerse Tools MCP - Security Documentation

## Overview

The RedVerse Tools MCP server supports two transport modes with different security models:

1. **stdio transport** (default): Local use only, no network exposure, no authentication required
2. **sse transport**: HTTP-based, network-exposed, **requires API key authentication**

## Security Model

### stdio Mode (Local Use)
- **Default mode** when no `--transport` flag is specified
- Communication via standard input/output pipes
- No network listener, no remote access possible
- **No authentication required** - safe for local AI clients like Claude Desktop, Ollama

### SSE Mode (Network Exposed)
- Enabled with `--transport sse` flag
- Binds HTTP listener to `0.0.0.0` by default (all network interfaces)
- **Requires API key authentication** for all tool invocations
- API key must be provided via `X-API-Key` HTTP header
- Uses constant-time comparison to prevent timing attacks

## Configuration

### Setting Up SSE Mode with Authentication

1. **Generate a secure API key:**
   ```bash
   python -c 'import secrets; print(secrets.token_urlsafe(32))'
   ```

2. **Set the API key as an environment variable:**
   ```bash
   export REDVERSE_MCP_API_KEY='your-generated-key-here'
   ```

3. **Start the server in SSE mode:**
   ```bash
   python redverse_tools_mcp.py --transport sse --host 0.0.0.0 --port 8942
   ```

### Security Validation

The server will **refuse to start** in SSE mode if `REDVERSE_MCP_API_KEY` is not set:

```
[SECURITY ERROR] SSE transport requires authentication.
Set REDVERSE_MCP_API_KEY environment variable before starting.

Example:
  export REDVERSE_MCP_API_KEY='your-secret-key-here'
  python redverse_tools_mcp.py --transport sse

Generate a secure key with:
  python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

## Client Authentication

When connecting to an SSE-mode server, clients must include the API key in their requests:

### Using X-API-Key Header
```bash
curl -H "X-API-Key: your-api-key-here" \
     http://localhost:8942/tools/list_launcher_tools
```

### Using Authorization Header (Bearer Token)
```bash
curl -H "Authorization: Bearer your-api-key-here" \
     http://localhost:8942/tools/list_launcher_tools
```

## Authentication Enforcement

All tool invocations are protected:

1. **Dynamically registered launcher tools** - All `.sh` launchers discovered from the launchers folder
2. **Built-in meta tools:**
   - `list_launcher_tools` - List available tools
   - `reload_launcher_tools` - Reload launcher scripts
   - `inspect_launcher_tool` - Get tool details

### Authentication Failure Response

If authentication fails, tools return a JSON error response:

```json
{
  "success": false,
  "error": "Authentication required. Provide valid API key via X-API-Key header.",
  "error_type": "authentication_error"
}
```

## Security Best Practices

1. **Never commit API keys to version control**
   - Use environment variables
   - Add `.env` files to `.gitignore`

2. **Use strong, randomly generated keys**
   - Minimum 32 bytes of entropy
   - Use `secrets.token_urlsafe()` or similar cryptographic random generator

3. **Rotate keys periodically**
   - Change API keys on a regular schedule
   - Immediately rotate if compromise is suspected

4. **Restrict network access**
   - Use firewall rules to limit which IPs can connect
   - Consider using `--host 127.0.0.1` for localhost-only access
   - Use reverse proxy with additional authentication layers for production

5. **Monitor access logs**
   - Track failed authentication attempts
   - Alert on suspicious patterns

6. **Use TLS/HTTPS in production**
   - Deploy behind a reverse proxy (nginx, Apache, Caddy)
   - Enable HTTPS to encrypt API keys in transit
   - Never send API keys over unencrypted HTTP on untrusted networks

## Migration Guide

### Existing Deployments

If you have an existing deployment using SSE mode without authentication:

1. **Generate an API key** (see Configuration section above)
2. **Set the environment variable** before starting the server
3. **Update all clients** to include the API key in their requests
4. **Test authentication** before deploying to production

### Backward Compatibility

- **stdio mode**: No changes required, works exactly as before
- **SSE mode**: Now requires `REDVERSE_MCP_API_KEY` environment variable

## Threat Model

### Mitigated Threats

✅ **Unauthenticated remote code execution** - API key prevents unauthorized tool invocation  
✅ **Network-based attacks** - Authentication required for all SSE transport operations  
✅ **Timing attacks** - Constant-time comparison prevents key extraction via timing analysis

### Remaining Considerations

⚠️ **API key compromise** - If key is leaked, attacker gains full access until key is rotated  
⚠️ **Man-in-the-middle attacks** - Use HTTPS/TLS to prevent key interception  
⚠️ **Launcher script vulnerabilities** - Validate and audit all `.sh` scripts in launchers folder  
⚠️ **Parameter injection** - Launcher scripts should validate all input parameters

## Support

For security issues or questions:
- Review this documentation
- Check server logs for authentication errors
- Ensure `REDVERSE_MCP_API_KEY` is set correctly
- Verify client is sending API key in correct header format
