# Security Patch Summary - RedVerse Tools MCP

## Vulnerability Fixed
**Title:** SSE transport exposes launcher tool execution without authentication  
**Severity:** High  
**File:** redverse_tools_mcp.py

## Root Cause
The MCP server exposed launcher-backed tools over SSE transport (HTTP) without any authentication mechanism. When started with `--transport sse`, the server bound to `0.0.0.0` by default, allowing any network client to invoke registered launcher tools and execute shell scripts with attacker-supplied parameters.

## Security Impact
- **Before Fix:** Unauthenticated remote code execution via launcher tool invocation
- **Attack Vector:** Network-accessible HTTP endpoint with no authentication
- **Scope:** All registered launcher tools and meta tools (list, reload, inspect)

## Changes Implemented

### 1. API Key Authentication (Lines 39-44)
```python
# API Key for SSE transport authentication
# REQUIRED when using --transport sse to prevent unauthenticated access
MCP_API_KEY = os.environ.get("REDVERSE_MCP_API_KEY", "")

# Track which transport mode we're running in
_TRANSPORT_MODE: str = "stdio"
```

### 2. Authentication Validation Function (Lines 206-247)
- Added `AuthenticationError` exception class
- Implemented `validate_api_key(ctx)` function
- Checks transport mode (stdio = no auth, sse = require auth)
- Validates API key from request headers (X-API-Key or Authorization)
- Uses `secrets.compare_digest()` for constant-time comparison (prevents timing attacks)

### 3. Protected Tool Execution (Lines 268-277)
- Modified `execute_launcher()` to validate authentication before execution
- Returns JSON error response on authentication failure
- Includes error_type field for client-side handling

### 4. Protected Meta Tools (Lines 461-469, 519-527, 572-580)
- Added authentication checks to `list_launcher_tools()`
- Added authentication checks to `reload_launcher_tools()`
- Added authentication checks to `inspect_launcher_tool()`

### 5. Startup Security Validation (Lines 634-656)
- Server refuses to start in SSE mode without `REDVERSE_MCP_API_KEY`
- Displays clear error message with setup instructions
- Shows security status on successful startup
- Provides key generation command

### 6. Documentation
- Created `SECURITY_MCP.md` with comprehensive security documentation
- Created `test_mcp_auth.sh` for testing authentication enforcement
- Updated module docstring to indicate authentication requirement

## Security Properties

### Defense in Depth
1. **Startup validation:** Server won't start in SSE mode without API key
2. **Per-request validation:** Every tool invocation checks authentication
3. **Constant-time comparison:** Prevents timing-based key extraction
4. **Clear error messages:** Helps legitimate users configure correctly

### Backward Compatibility
- **stdio mode:** No changes, works exactly as before (local use, no auth needed)
- **SSE mode:** Now requires `REDVERSE_MCP_API_KEY` environment variable

### Threat Mitigation
✅ Unauthenticated remote code execution  
✅ Network-based attacks on tool invocation  
✅ Timing attacks on authentication  
✅ Accidental exposure without authentication  

## Usage

### Secure SSE Mode Setup
```bash
# Generate secure API key
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# Set environment variable
export REDVERSE_MCP_API_KEY='generated-key-here'

# Start server
python redverse_tools_mcp.py --transport sse
```

### Client Authentication
```bash
# Using X-API-Key header
curl -H "X-API-Key: your-key" http://localhost:8942/tools/list_launcher_tools

# Using Authorization header
curl -H "Authorization: Bearer your-key" http://localhost:8942/tools/list_launcher_tools
```

## Testing
Run the test script to verify authentication enforcement:
```bash
bash test_mcp_auth.sh
```

## Deployment Recommendations

1. **Always use strong, randomly generated API keys** (minimum 32 bytes entropy)
2. **Never commit API keys to version control**
3. **Use HTTPS/TLS in production** (deploy behind reverse proxy)
4. **Rotate keys periodically**
5. **Monitor for failed authentication attempts**
6. **Restrict network access** with firewall rules
7. **Consider localhost-only binding** (`--host 127.0.0.1`) when possible

## Files Modified
- `redverse_tools_mcp.py` - Added authentication system

## Files Created
- `SECURITY_MCP.md` - Security documentation
- `test_mcp_auth.sh` - Authentication test script
- `SECURITY_PATCH_SUMMARY.md` - This file

## Verification
The fix has been implemented with the following verification:
- ✅ Authentication validation function implemented
- ✅ All tool handlers protected (launcher tools + meta tools)
- ✅ Startup validation prevents unauthenticated SSE mode
- ✅ Constant-time comparison prevents timing attacks
- ✅ stdio mode unchanged (backward compatible)
- ✅ Clear error messages for configuration issues
- ✅ Comprehensive documentation provided

## Security Review Checklist
- [x] Authentication required for all SSE transport operations
- [x] API key validated before any tool execution
- [x] Constant-time comparison prevents timing attacks
- [x] Server refuses to start without API key in SSE mode
- [x] stdio mode remains unchanged (local use)
- [x] Clear documentation for secure deployment
- [x] Test script provided for validation
- [x] Error messages don't leak sensitive information
- [x] No hardcoded credentials
- [x] Environment variable used for secret management
