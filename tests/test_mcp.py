"""MCP protocol + stdio framing tests (offline, subprocess handshake)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server.py"
TOOL = ROOT / "ttagent.py"


def rpc(msgs):
    """Pipe newline-delimited requests through the server, collect replies."""
    stdin = "\n".join(json.dumps(m) for m in msgs) + "\n"
    p = subprocess.run([sys.executable, str(SERVER)], input=stdin,
                       capture_output=True, text=True, timeout=60)
    replies = [json.loads(ln) for ln in p.stdout.splitlines() if ln.strip()]
    return p, replies


class ProtocolTests(unittest.TestCase):
    def test_initialize_echoes_supported_version(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2024-11-05"}}])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "ttagent")

    def test_initialize_advertises_latest_when_unknown(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "1999-01-01"}}])
        self.assertEqual(replies[0]["result"]["protocolVersion"],
                         "2025-06-18")

    def test_ping(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 2, "method": "ping"}])
        self.assertEqual(replies[0]["result"], {})

    def test_tools_list_has_four_tools(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 3, "method": "tools/list"}])
        names = [t["name"] for t in replies[0]["result"]["tools"]]
        self.assertEqual(names, ["extract_video", "lookup_video",
                                 "read_manifest", "get_schema"])

    def test_get_schema_returns_draft07(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "get_schema", "arguments": {}}}])
        result = replies[0]["result"]
        self.assertFalse(result["isError"])
        doc = json.loads(result["content"][0]["text"])
        self.assertEqual(doc["$schema"],
                         "http://json-schema.org/draft-07/schema#")
        self.assertEqual(doc["properties"]["schema_version"]["const"], "1.0")

    def test_unknown_method(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 5,
                           "method": "no/such/method"}])
        self.assertEqual(replies[0]["error"]["code"], -32601)

    def test_parse_error_line(self):
        p = subprocess.run([sys.executable, str(SERVER)], input="{broken\n",
                           capture_output=True, text=True, timeout=60)
        reply = json.loads(p.stdout.splitlines()[0])
        self.assertEqual(reply["error"]["code"], -32700)

    def test_notification_is_silent(self):
        p, replies = rpc([{"jsonrpc": "2.0",
                           "method": "notifications/initialized"}])
        self.assertEqual(replies, [])

    def test_read_manifest_refuses_foreign_names(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                           "params": {"name": "read_manifest", "arguments":
                                      {"path": "/tmp/secret.json"}}}])
        result = replies[0]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("refusing", result["content"][0]["text"])

    def test_extract_video_invalid_params_is_error(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                           "params": {"name": "extract_video",
                                      "arguments": {}}}])
        self.assertTrue(replies[0]["result"]["isError"])

    def test_extract_video_invalid_input_maps_to_isError(self):
        p, replies = rpc([{"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                           "params": {"name": "extract_video",
                                      "arguments": {"url": "!!!"}}}])
        self.assertTrue(replies[0]["result"]["isError"])
        payload = json.loads(replies[0]["result"]["content"][0]["text"])
        self.assertEqual(payload["status"], "invalid_input")


class CoreVersionTests(unittest.TestCase):
    def test_core_version_matches_tool(self):
        sys.path.insert(0, str(ROOT))
        import mcp_server
        self.assertEqual(mcp_server._core_version(), "1.0.0")


if __name__ == "__main__":
    unittest.main()
