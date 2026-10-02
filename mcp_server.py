#!/usr/bin/env python3
"""
mcp_server.py — MCP (Model Context Protocol) wrapper for ttagent
================================================================
Exposes the ttagent CLI as MCP tools over the standard stdio transport,
so MCP-compatible agents (Claude, Zed, custom hosts) can harvest public
TikTok videos without touching a shell.

Design constraints (mirrors the core project):

  * stdlib only — no `mcp` package, no pip installs. The MCP stdio
    transport is newline-delimited JSON-RPC 2.0; that is simple enough
    to implement faithfully in ~200 lines.
  * The core CLI stays the single source of truth. This server never
    reimplements the pipeline: every tool call shells out to
    `ttagent.py` as a subprocess (argument list, never a shell) and
    returns its manifest. Process isolation also means a hung network
    call is bounded by a hard timeout + process kill.
  * Logs go to stderr. stdout carries ONLY protocol messages.

Tools:
  extract_post   — full harvest (decode → download, verified files)
  lookup_post    — metadata only (--no-download)
  read_manifest  — read + return an existing post_manifest.json
  get_schema     — return the JSON Schema for the manifest envelope

Error policy (honest results over fake success):
  * exit 0                      → isError: false, envelope attached
  * exit 1, status "empty"      → isError: false (honest negative result)
  * exit 2 / "invalid_input"    → isError: true  (bad tool arguments)
  * timeout / crash / unparseable → isError: true
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "ttagent.py"
SCHEMA = ROOT / "schema" / "video-result.schema.json"

# Protocol versions this server can speak. On initialize we echo the
# client's version when we support it, otherwise advertise our latest.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_PROTOCOL_VERSION = "2025-06-18"

SERVER_NAME = "ttagent"

# Hard wall-clock bounds per tool call (seconds).


def _env_timeout(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        log(f"ignoring non-integer {name}; using default {default}s")
        return default


EXTRACT_TIMEOUT = _env_timeout("TTAGENT_MCP_EXTRACT_TIMEOUT", 900)
LOOKUP_TIMEOUT = 120
MANIFEST_NAME = "video_manifest.json"

JSONRPC_PARSE_ERROR = -32700
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


def log(msg: str) -> None:
    """Server diagnostics — stderr only, stdout is protocol-exclusive."""
    print(f"[mcp] {msg}", file=sys.stderr)


# ── Core CLI invocation ──────────────────────────────────────────────────────
def _run_cli(args: list, timeout: int) -> subprocess.CompletedProcess:
    """Run ttagent.py as a subprocess (no shell, hard timeout)."""
    cmd = [sys.executable, str(TOOL), *args, "--json", "--quiet"]
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, check=False)


def _read_manifest(path_str: str):
    try:
        p = Path(path_str)
        if p.name != MANIFEST_NAME or not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _tool_result_from_run(proc: subprocess.CompletedProcess, out_dir: str) -> dict:
    """Map a finished CLI run to an MCP tool result.

    The CLI's stdout is a pipe-safe JSON summary; the full envelope lives
    in the manifest it points to. We attach the envelope verbatim — the
    MCP layer adds nothing to, and hides nothing from, the contract.
    """
    parsed = None
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    except ValueError:
        parsed = None

    if parsed is None:
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps({
                "error": "ttagent produced no parsable stdout summary",
                "exit_code": proc.returncode,
                "stderr_tail": (proc.stderr or "")[-2000:],
            })}],
        }

    if parsed.get("status") == "invalid_input":
        return {
            "isError": True,
            "content": [{"type": "text", "text": json.dumps(parsed)}],
        }

    envelope = _read_manifest(parsed.get("manifest_path", ""))
    payload = {
        "out_dir": out_dir,
        "manifest_path": parsed.get("manifest_path"),
        "summary": parsed,
        "envelope": envelope,  # None when the manifest could not be read —
        # the summary still tells the caller what happened
    }
    return {
        "isError": False,
        "content": [{"type": "text", "text": json.dumps(payload)}],
    }


def _harvest_tool(url: str, out_dir, download_media: bool, timeout: int) -> dict:
    """Shared body of extract_video / lookup_video."""
    if not isinstance(url, str) or not url.strip():
        return {"isError": True, "content": [{
            "type": "text",
            "text": "invalid params: 'url' (string) is required"}]}
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="ttagent-mcp-")
    if not isinstance(out_dir, str) or not out_dir.strip():
        return {"isError": True, "content": [{
            "type": "text",
            "text": "invalid params: 'out_dir' must be a non-empty string"}]}

    args = [url.strip(), "--out", out_dir]
    if not download_media:
        args.append("--no-download")
    try:
        proc = _run_cli(args, timeout)
    except subprocess.TimeoutExpired:
        return {"isError": True, "content": [{
            "type": "text",
            "text": f"ttagent timed out after {timeout}s "
                    f"({'download aborted' if download_media else 'metadata lookup'}); "
                    f"try lookup_post (metadata only) or a direct CLI run"}]}
    except OSError as e:
        return {"isError": True, "content": [{
            "type": "text", "text": f"failed to launch ttagent: {e}"}]}
    return _tool_result_from_run(proc, out_dir)


def _read_manifest_tool(path: str) -> dict:
    if not isinstance(path, str) or not path.strip():
        return {"isError": True, "content": [{
            "type": "text",
            "text": "invalid params: 'path' (string) is required"}]}
    p = Path(path.strip())
    if p.name != MANIFEST_NAME:
        return {"isError": True, "content": [{
            "type": "text",
            "text": f"refusing: this tool reads {MANIFEST_NAME} files only "
                    f"(got '{p.name}')"}]}
    env = _read_manifest(str(p))
    if env is None:
        return {"isError": True, "content": [{
            "type": "text",
            "text": f"manifest not found or not valid JSON: {p}"}]}
    return {"isError": False,
            "content": [{"type": "text", "text": json.dumps(env)}]}


def _get_schema_tool() -> dict:
    try:
        doc = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"isError": True, "content": [{
            "type": "text", "text": f"schema unavailable: {e}"}]}
    return {"isError": False,
            "content": [{"type": "text", "text": json.dumps(doc)}]}


# ── Tool registry ────────────────────────────────────────────────────────────
def _bool_arg(args: dict, key: str, default: bool) -> bool:
    """Accept real JSON booleans; tolerate 'true'/'false' strings; anything
    else falls back to the documented default (never silently inverted)."""
    v = args.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    return default


TOOLS = [
    {
        "name": "extract_video",
        "description": (
            "Harvest a public TikTok video: given a video/photo URL, "
            "short link or bare video id, decodes the public surface and "
            "downloads the video (HD when exposed), the soundtrack and "
            "covers (all magic-byte verified) to out_dir. Returns the "
            "summary plus the full video_manifest envelope (author, title, "
            "stats, music identity, media URLs, local files, errors, "
            "decode-slot provenance). No login, no API keys."),
        "inputSchema": {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string",
                        "description": "TikTok video/photo URL, short link, "
                                       "or bare video id"},
                "out_dir": {"type": "string",
                            "description": "output directory; a fresh temp dir when omitted"},
                "download_media": {"type": "boolean", "default": True,
                                   "description": "false = manifest only, no files on disk"},
            },
        },
    },
    {
        "name": "lookup_video",
        "description": (
            "Fast metadata-only lookup of a public TikTok video: same "
            "decode pipeline as extract_video but with --no-download — "
            "author, title, stats, music identity, media URLs, without "
            "writing media files. Use this when you only need to read "
            "the video."),
        "inputSchema": {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string",
                        "description": "TikTok video/photo URL, short link, "
                                       "or bare video id"},
                "out_dir": {"type": "string",
                            "description": "output directory for the manifest; "
                                           "temp dir when omitted"},
            },
        },
    },
    {
        "name": "read_manifest",
        "description": (
            "Read an existing video_manifest.json produced by a previous "
            "extract/lookup and return the full envelope. Refuses any "
            "file not named video_manifest.json."),
        "inputSchema": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string",
                         "description": "absolute path to a video_manifest.json"},
            },
        },
    },
    {
        "name": "get_schema",
        "description": (
            "Return the JSON Schema (draft-07) describing the "
            "video_manifest envelope (schema_version 1.0) — use it to "
            "validate or explore the output contract."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(name: str, args: dict) -> dict:
    if name == "extract_video":
        return _harvest_tool(args.get("url"), args.get("out_dir"),
                             _bool_arg(args, "download_media", True),
                             EXTRACT_TIMEOUT)
    if name == "lookup_video":
        return _harvest_tool(args.get("url"), args.get("out_dir"),
                             False, LOOKUP_TIMEOUT)
    if name == "read_manifest":
        return _read_manifest_tool(args.get("path"))
    if name == "get_schema":
        return _get_schema_tool()
    return {"isError": True, "content": [{
        "type": "text", "text": f"unknown tool: {name}"}]}


# ── MCP protocol plumbing (JSON-RPC 2.0, newline-delimited stdio) ───────────
def _resp(req_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}


def handle_request(msg: dict):
    """Dispatch one decoded JSON-RPC message. Returns the response object,
    or None for notifications (messages without an id)."""
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        requested = msg.get("params", {}).get("protocolVersion")
        version = (requested if requested in SUPPORTED_PROTOCOL_VERSIONS
                   else LATEST_PROTOCOL_VERSION)
        return _resp(req_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME,
                           "version": _core_version()},
        })
    if method == "ping":
        return _resp(req_id, {})
    if method == "tools/list":
        return _resp(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _err(req_id, JSONRPC_INVALID_PARAMS,
                        "arguments must be an object")
        result = call_tool(name, args)
        return _resp(req_id, result)
    if req_id is None:
        # A notification we do not need to act on (e.g. notifications/initialized)
        return None
    return _err(req_id, JSONRPC_METHOD_NOT_FOUND, f"unknown method: {method}")


def _core_version() -> str:
    try:
        proc = subprocess.run([sys.executable, str(TOOL), "--version"],
                              capture_output=True, text=True, timeout=30,
                              check=False)
        v = proc.stdout.strip()
        # argparse's --version prints "<prog> <semver>"; keep the semver.
        if v:
            return v.split()[-1]
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def serve() -> int:
    """Main loop: read newline-delimited JSON-RPC from stdin, write
    responses to stdout. Exits cleanly on EOF or a disconnected client."""
    log(f"{SERVER_NAME} MCP server ready (protocol versions: "
        f"{', '.join(SUPPORTED_PROTOCOL_VERSIONS)})")
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                _emit(_err(None, JSONRPC_PARSE_ERROR,
                           "parse error: request line is not valid JSON"))
                continue
            if not isinstance(msg, dict):
                _emit(_err(None, JSONRPC_PARSE_ERROR,
                           "parse error: request must be a JSON object"))
                continue
            try:
                response = handle_request(msg)
            except Exception as e:  # noqa: BLE001 — the server must never crash
                log(f"internal error handling {msg.get('method')}: {e}")
                req_id = msg.get("id")
                if req_id is not None:
                    _emit(_err(req_id, JSONRPC_INTERNAL_ERROR,
                               f"internal error: {type(e).__name__}"))
                continue
            if response is not None:
                _emit(response)
    except (BrokenPipeError, KeyboardInterrupt, OSError):
        # Client hung up (or the host shut down) — exit quietly, as an MCP
        # server should. Never print a traceback to stdout.
        return 0
    return 0


def _emit(response: dict) -> None:
    """Write one protocol message to stdout (single line, flushed)."""
    print(json.dumps(response), flush=True)


if __name__ == "__main__":
    sys.exit(serve())
