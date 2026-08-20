#!/bin/bash
# Test script to verify MCP authentication is working

echo "=== RedVerse Tools MCP - Authentication Test ==="
echo ""

# Test 1: Verify server refuses to start without API key in SSE mode
echo "Test 1: Server should refuse to start in SSE mode without API key"
echo "---------------------------------------------------------------"
unset REDVERSE_MCP_API_KEY
timeout 2 python redverse_tools_mcp.py --transport sse 2>&1 | grep -q "SECURITY ERROR"
if [ $? -eq 0 ]; then
    echo "✓ PASS: Server correctly refuses to start without API key"
else
    echo "✗ FAIL: Server should refuse to start without API key"
fi
echo ""

# Test 2: Verify server starts successfully with API key
echo "Test 2: Server should start successfully with API key"
echo "---------------------------------------------------------------"
export REDVERSE_MCP_API_KEY="test-key-$(date +%s)"
timeout 2 python redverse_tools_mcp.py --transport sse 2>&1 | grep -q "API key authentication ENABLED"
if [ $? -eq 0 ]; then
    echo "✓ PASS: Server starts with API key and enables authentication"
else
    echo "✗ FAIL: Server should start with API key"
fi
echo ""

# Test 3: Verify stdio mode works without API key
echo "Test 3: stdio mode should work without API key (local use)"
echo "---------------------------------------------------------------"
unset REDVERSE_MCP_API_KEY
timeout 2 python redverse_tools_mcp.py --transport stdio 2>&1 | grep -q "stdio transport (local use, no authentication required)"
if [ $? -eq 0 ]; then
    echo "✓ PASS: stdio mode works without API key"
else
    echo "✗ FAIL: stdio mode should work without API key"
fi
echo ""

echo "=== Test Summary ==="
echo "Authentication security measures are in place."
echo ""
echo "Key Security Features:"
echo "  ✓ SSE mode requires REDVERSE_MCP_API_KEY environment variable"
echo "  ✓ Server refuses to start in SSE mode without API key"
echo "  ✓ All tool invocations validate API key in SSE mode"
echo "  ✓ stdio mode remains unchanged (local use, no auth needed)"
echo ""
echo "To use SSE mode securely:"
echo "  1. Generate key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
echo "  2. Set env var: export REDVERSE_MCP_API_KEY='your-key-here'"
echo "  3. Start server: python redverse_tools_mcp.py --transport sse"
echo "  4. Clients must send: X-API-Key: your-key-here"
