#!/usr/bin/env python3
"""
RedVerse Tools MCP Server
=========================
Dynamically discovers .sh launcher files from a folder and exposes them
as MCP tools. Drop a .sh file in the launchers/ folder, it becomes a tool.

Each .sh file must follow the RedVerse Launcher Protocol (RLP) header format.
See launchers/TEMPLATE.sh for the full spec.

Transport: stdio (local use with Ollama, Claude Desktop, etc.)
          sse (HTTP, requires REDVERSE_MCP_API_KEY for authentication)
"""

import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# Default launchers folder — override with env var REDVERSE_LAUNCHERS_DIR
DEFAULT_LAUNCHERS_DIR = Path(__file__).parent / "launchers"
LAUNCHERS_DIR = Path(os.environ.get("REDVERSE_LAUNCHERS_DIR", DEFAULT_LAUNCHERS_DIR))

TOOL_EXECUTION_TIMEOUT = int(os.environ.get("REDVERSE_TOOL_TIMEOUT", "30"))  # seconds

# API Key for SSE transport authentication
# REQUIRED when using --transport sse to prevent unauthenticated access
MCP_API_KEY = os.environ.get("REDVERSE_MCP_API_KEY", "")

# Track which transport mode we're running in
_TRANSPORT_MODE: str = "stdio"

# ─────────────────────────────────────────────
# RLP HEADER PARSER
# RedVerse Launcher Protocol — the comment spec
# for how a .sh file describes itself to the MCP
# ─────────────────────────────────────────────

@dataclass
class LauncherParam:
    """A single parameter declared in a launcher's RLP header."""
    name: str
    type: str           # str | int | float | bool
    required: bool
    description: str
    default: Optional[str] = None


@dataclass
class LauncherSpec:
    """Full parsed spec from a .sh launcher file's RLP header."""
    tool_name: str
    description: str
    params: List[LauncherParam]
    output_description: str
    tags: List[str]
    script_path: Path
    raw_header: str = ""

    # Maps RLP type strings to Python types (for Pydantic schema generation)
    TYPE_MAP: Dict[str, Any] = field(default_factory=lambda: {
        "str":   str,
        "string": str,
        "int":   int,
        "integer": int,
        "float": float,
        "number": float,
        "bool":  bool,
        "boolean": bool,
    })


def parse_rlp_header(script_path: Path) -> Optional[LauncherSpec]:
    """
    Parse the RLP (RedVerse Launcher Protocol) header from a .sh file.

    Expected format in the .sh header:
        # @TOOL:    my_tool_name
        # @DESC:    What this tool does for the AI
        # @PARAM:   param_name:str:required:Description of this param
        # @PARAM:   optional_flag:bool:optional:Some optional param
        # @OUTPUT:  What gets returned — stdout of the script
        # @TAGS:    tag1,tag2,tag3
    """
    try:
        content = script_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[RLP] Could not read {script_path}: {e}", file=sys.stderr)
        return None

    lines = content.splitlines()
    header_lines = []

    # Collect all comment lines at the top (stop at first non-comment, non-blank line)
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            header_lines.append(stripped)
        elif stripped.startswith("#!/"):
            header_lines.append(stripped)
        else:
            # First real code line — stop collecting header
            if header_lines:
                break

    header_text = "\n".join(header_lines)

    def extract(tag: str) -> Optional[str]:
        pattern = rf"#\s*@{tag}:\s*(.+)"
        match = re.search(pattern, header_text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def extract_all(tag: str) -> List[str]:
        pattern = rf"#\s*@{tag}:\s*(.+)"
        return [m.group(1).strip() for m in re.finditer(pattern, header_text, re.IGNORECASE)]

    tool_name = extract("TOOL")
    description = extract("DESC")

    if not tool_name or not description:
        print(
            f"[RLP] Skipping {script_path.name} — missing @TOOL or @DESC header",
            file=sys.stderr
        )
        return None

    # Sanitize tool name — MCP wants snake_case alphanumeric
    tool_name = re.sub(r"[^a-z0-9_]", "_", tool_name.lower()).strip("_")

    # Parse @PARAM lines: name:type:required|optional:description
    params: List[LauncherParam] = []
    for param_str in extract_all("PARAM"):
        parts = param_str.split(":", 3)
        if len(parts) < 4:
            print(
                f"[RLP] Warning: malformed @PARAM in {script_path.name}: '{param_str}' "
                f"(expected name:type:required|optional:description)",
                file=sys.stderr
            )
            continue
        p_name, p_type, p_req, p_desc = [p.strip() for p in parts]
        params.append(LauncherParam(
            name=p_name.lower(),
            type=p_type.lower(),
            required=(p_req.lower() == "required"),
            description=p_desc,
        ))

    output_desc = extract("OUTPUT") or "stdout output from the script"
    tags_raw = extract("TAGS") or ""
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    return LauncherSpec(
        tool_name=tool_name,
        description=description,
        params=params,
        output_description=output_desc,
        tags=tags,
        script_path=script_path,
        raw_header=header_text,
    )


# ─────────────────────────────────────────────
# LAUNCHER DISCOVERY
# ─────────────────────────────────────────────

def discover_launchers(launchers_dir: Path) -> List[LauncherSpec]:
    """Scan launchers_dir for .sh files and parse their RLP headers."""
    if not launchers_dir.exists():
        print(f"[Discovery] Launchers dir not found: {launchers_dir}", file=sys.stderr)
        launchers_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Discovery] Created: {launchers_dir}", file=sys.stderr)
        return []

    found = []
    for sh_file in sorted(launchers_dir.glob("*.sh")):
        if sh_file.name.startswith("_") or sh_file.name.startswith("TEMPLATE"):
            continue  # Skip template/private files
        spec = parse_rlp_header(sh_file)
        if spec:
            found.append(spec)
            print(f"[Discovery] Loaded tool '{spec.tool_name}' from {sh_file.name}", file=sys.stderr)

    print(f"[Discovery] Total tools loaded: {len(found)}", file=sys.stderr)
    return found


# ─────────────────────────────────────────────
# AUTHENTICATION
# ─────────────────────────────────────────────

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def validate_api_key(ctx: Optional[Context]) -> None:
    """
    Validate API key for SSE transport mode.
    
    In stdio mode (local use), no authentication is required.
    In SSE mode (network exposed), API key must be provided via X-API-Key header.
    
    Raises:
        AuthenticationError: If authentication fails in SSE mode.
    """
    # stdio mode: local use, no authentication needed
    if _TRANSPORT_MODE == "stdio":
        return
    
    # SSE mode: require API key authentication
    if not MCP_API_KEY:
        raise AuthenticationError(
            "Server misconfiguration: REDVERSE_MCP_API_KEY not set. "
            "SSE transport requires API key authentication."
        )
    
    # Extract API key from context metadata
    # FastMCP passes request headers through context
    provided_key = None
    if ctx and hasattr(ctx, 'meta') and ctx.meta:
        # Check for API key in various header formats
        provided_key = (
            ctx.meta.get('x-api-key') or 
            ctx.meta.get('X-API-Key') or
            ctx.meta.get('authorization', '').replace('Bearer ', '').strip()
        )
    
    # Constant-time comparison to prevent timing attacks
    if not provided_key or not secrets.compare_digest(provided_key, MCP_API_KEY):
        raise AuthenticationError(
            "Authentication required. Provide valid API key via X-API-Key header."
        )


# ─────────────────────────────────────────────
# SCRIPT EXECUTION ENGINE
# ─────────────────────────────────────────────

async def execute_launcher(
    spec: LauncherSpec,
    args: Dict[str, Any],
    ctx: Optional[Context] = None,
) -> str:
    """
    Execute a .sh launcher with provided args.
    Args are injected as environment variables: PARAM_<NAME> (uppercased).

    Example: param 'plant_id' becomes env var PARAM_PLANT_ID
    
    Raises:
        AuthenticationError: If authentication fails in SSE mode.
    """
    # Validate authentication before executing any launcher
    try:
        validate_api_key(ctx)
    except AuthenticationError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "tool": spec.tool_name,
            "error_type": "authentication_error",
        }, indent=2)
    
    # Build environment: inherit current env + inject params
    env = os.environ.copy()

    for param in spec.params:
        env_key = f"PARAM_{param.name.upper()}"
        value = args.get(param.name)
        if value is not None:
            env[env_key] = str(value)
        elif param.default is not None:
            env[env_key] = str(param.default)
        else:
            env[env_key] = ""  # Optional param not provided → empty string

    # Also inject a JSON blob of all params for scripts that prefer that
    env["PARAMS_JSON"] = json.dumps(
        {p.name: args.get(p.name, "") for p in spec.params},
        default=str
    )
    env["TOOL_NAME"] = spec.tool_name

    script = str(spec.script_path.resolve())

    # Ensure the script is executable
    try:
        spec.script_path.chmod(spec.script_path.stat().st_mode | 0o111)
    except Exception:
        pass

    if ctx:
        await ctx.report_progress(0.1, f"Launching {spec.tool_name}...")

    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            script,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=TOOL_EXECUTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return json.dumps({
                "success": False,
                "error": f"Tool '{spec.tool_name}' timed out after {TOOL_EXECUTION_TIMEOUT}s",
                "tool": spec.tool_name,
            }, indent=2)

        if ctx:
            await ctx.report_progress(0.9, "Processing output...")

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        result: Dict[str, Any] = {
            "success": proc.returncode == 0,
            "tool": spec.tool_name,
            "exit_code": proc.returncode,
            "output": stdout_text,
        }

        if stderr_text:
            result["stderr"] = stderr_text

        # Try to return raw output if it's already valid JSON
        try:
            parsed = json.loads(stdout_text)
            result["output"] = parsed
            result["output_was_json"] = True
        except (json.JSONDecodeError, ValueError):
            pass

        return json.dumps(result, indent=2, default=str)

    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "error": f"Script not found at: {script}",
            "tool": spec.tool_name,
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Execution error: {type(e).__name__}: {e}",
            "tool": spec.tool_name,
        }, indent=2)


# ─────────────────────────────────────────────
# MCP SERVER SETUP
# ─────────────────────────────────────────────

mcp = FastMCP("redverse_tools_mcp")

# Track loaded specs globally so the reload tool can access them
_loaded_specs: List[LauncherSpec] = []


def build_tool_docstring(spec: LauncherSpec) -> str:
    """Generate a rich docstring for an MCP tool from its LauncherSpec."""
    lines = [spec.description, ""]
    if spec.params:
        lines.append("Parameters (passed as env vars PARAM_<NAME> to the script):")
        for p in spec.params:
            req = "required" if p.required else "optional"
            lines.append(f"  - {p.name} ({p.type}, {req}): {p.description}")
    lines.append("")
    lines.append(f"Returns: {spec.output_description}")
    if spec.tags:
        lines.append(f"Tags: {', '.join(spec.tags)}")
    return "\n".join(lines)


def register_launcher_as_tool(spec: LauncherSpec) -> None:
    """
    Dynamically register a LauncherSpec as a FastMCP tool.
    Uses closure capture to bind each spec to its handler.
    """

    # Build a Pydantic input model dynamically from the spec's params
    field_definitions: Dict[str, Any] = {}
    for p in spec.params:
        py_type = LauncherSpec.TYPE_MAP.fget(None) if False else {  # type: ignore
            "str": str, "string": str,
            "int": int, "integer": int,
            "float": float, "number": float,
            "bool": bool, "boolean": bool,
        }.get(p.type, str)

        if p.required:
            field_definitions[p.name] = (py_type, Field(..., description=p.description))
        else:
            field_definitions[p.name] = (Optional[py_type], Field(default=None, description=p.description))

    # Capture spec in closure
    captured_spec = spec

    async def tool_handler(ctx: Context, **kwargs: Any) -> str:
        return await execute_launcher(captured_spec, kwargs, ctx)

    tool_handler.__doc__ = build_tool_docstring(spec)
    tool_handler.__name__ = spec.tool_name

    # Register with FastMCP
    mcp.add_tool(
        tool_handler,
        name=spec.tool_name,
        description=spec.description,
    )


# ─────────────────────────────────────────────
# BUILT-IN META TOOLS
# (these always exist regardless of launcher folder)
# ─────────────────────────────────────────────

class ListToolsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verbose: bool = Field(default=False, description="Show full param details for each tool")


@mcp.tool(
    name="list_launcher_tools",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def list_launcher_tools(params: ListToolsInput, ctx: Context = None) -> str:
    """
    List all tools currently loaded from the launchers folder.
    Use this to discover available shell tools without needing to know them in advance.

    Returns: JSON list of tool names, descriptions, params, and script paths.
    """
    # Validate authentication
    try:
        validate_api_key(ctx)
    except AuthenticationError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "authentication_error",
        }, indent=2)
    
    result = []
    for spec in _loaded_specs:
        entry: Dict[str, Any] = {
            "tool_name": spec.tool_name,
            "description": spec.description,
            "script": str(spec.script_path.name),
            "tags": spec.tags,
            "output": spec.output_description,
        }
        if params.verbose:
            entry["params"] = [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "description": p.description,
                }
                for p in spec.params
            ]
        result.append(entry)

    return json.dumps({
        "launchers_dir": str(LAUNCHERS_DIR),
        "tool_count": len(result),
        "tools": result,
    }, indent=2)


class ReloadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@mcp.tool(
    name="reload_launcher_tools",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def reload_launcher_tools(params: ReloadInput, ctx: Context = None) -> str:
    """
    Rescan the launchers folder and reload all .sh tools without restarting the server.
    Use this after adding or modifying launcher scripts.

    Returns: JSON summary of what was loaded/reloaded.
    """
    # Validate authentication
    try:
        validate_api_key(ctx)
    except AuthenticationError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "authentication_error",
        }, indent=2)
    
    global _loaded_specs
    old_names = {s.tool_name for s in _loaded_specs}
    _loaded_specs = discover_launchers(LAUNCHERS_DIR)
    new_names = {s.tool_name for s in _loaded_specs}

    added = new_names - old_names
    removed = old_names - new_names

    # Re-register all dynamically loaded tools
    for spec in _loaded_specs:
        register_launcher_as_tool(spec)

    return json.dumps({
        "success": True,
        "launchers_dir": str(LAUNCHERS_DIR),
        "total_tools": len(_loaded_specs),
        "tools_added": list(added),
        "tools_removed": list(removed),
        "all_tools": [s.tool_name for s in _loaded_specs],
    }, indent=2)


class InspectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str = Field(..., description="The tool name to inspect")


@mcp.tool(
    name="inspect_launcher_tool",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def inspect_launcher_tool(params: InspectInput, ctx: Context = None) -> str:
    """
    Get full details about a specific launcher tool including its RLP header and script path.
    Use this before calling a tool to understand its expected inputs.

    Returns: JSON with full spec, param list, and the raw RLP header text.
    """
    # Validate authentication
    try:
        validate_api_key(ctx)
    except AuthenticationError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "authentication_error",
        }, indent=2)
    
    for spec in _loaded_specs:
        if spec.tool_name == params.tool_name:
            return json.dumps({
                "tool_name": spec.tool_name,
                "description": spec.description,
                "script_path": str(spec.script_path),
                "output": spec.output_description,
                "tags": spec.tags,
                "params": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "description": p.description,
                        "env_var": f"PARAM_{p.name.upper()}",
                    }
                    for p in spec.params
                ],
                "rlp_header": spec.raw_header,
            }, indent=2)

    return json.dumps({
        "error": f"Tool '{params.tool_name}' not found",
        "available_tools": [s.tool_name for s in _loaded_specs],
    }, indent=2)


# ─────────────────────────────────────────────
# STARTUP — scan and register launchers
# ─────────────────────────────────────────────

def startup_load_launchers() -> None:
    global _loaded_specs
    _loaded_specs = discover_launchers(LAUNCHERS_DIR)
    for spec in _loaded_specs:
        register_launcher_as_tool(spec)


if __name__ == "__main__":
    import argparse as _argparse
    _p = _argparse.ArgumentParser(description="RedVerse Tools MCP Server")
    _p.add_argument("--transport", default="stdio", choices=["stdio", "sse"],
                    help="Transport mode: stdio (default) or sse (HTTP, for dashboard)")
    _p.add_argument("--port", type=int, default=8942,
                    help="HTTP port for SSE mode (default: 8942)")
    _p.add_argument("--host", default="0.0.0.0",
                    help="Host for SSE mode (default: 0.0.0.0)")
    _args = _p.parse_args()

    # Set transport mode globally
    _TRANSPORT_MODE = _args.transport

    # Security check: SSE mode requires API key
    if _args.transport == "sse":
        if not MCP_API_KEY:
            print(
                "[SECURITY ERROR] SSE transport requires authentication.\n"
                "Set REDVERSE_MCP_API_KEY environment variable before starting.\n"
                "\n"
                "Example:\n"
                "  export REDVERSE_MCP_API_KEY='your-secret-key-here'\n"
                "  python redverse_tools_mcp.py --transport sse\n"
                "\n"
                "Generate a secure key with:\n"
                "  python -c 'import secrets; print(secrets.token_urlsafe(32))'\n",
                file=sys.stderr
            )
            sys.exit(1)
        
        print(
            f"[redverse_tools_mcp] SSE transport: http://{_args.host}:{_args.port}\n"
            f"[SECURITY] API key authentication ENABLED\n"
            f"[SECURITY] Clients must provide X-API-Key header for all requests",
            file=sys.stderr
        )

    # Ensure launchers directory exists
    LAUNCHERS_DIR.mkdir(parents=True, exist_ok=True)

    startup_load_launchers()
    if _args.transport == "sse":
        mcp.run(transport="sse", host=_args.host, port=_args.port)
    else:
        print("[redverse_tools_mcp] stdio transport (local use, no authentication required)", file=sys.stderr)
        mcp.run()  # stdio transport — pipe it from your AI client
