"""Tests for the warden CLI helpers: preset resolution, liveness probe, token."""
import os
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import warden  # noqa: E402


class ProbeHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.send_response(403)  # engine's answer to an unsigned webhook
        self.end_headers()


class WardenTest(unittest.TestCase):
    def test_resolve_preset_precedence(self):
        self.assertEqual(warden.resolve_preset("cli", "env", "toml"), "cli")
        self.assertEqual(warden.resolve_preset(None, "env", "toml"), "env")
        self.assertEqual(warden.resolve_preset(None, None, "toml"), "toml")
        self.assertEqual(warden.resolve_preset(None, None, None), "local-fast")

    def test_probe_server_up_when_http_error_response(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), ProbeHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            self.assertTrue(warden.probe_server(port, timeout=3))
        finally:
            srv.shutdown()

    def test_probe_server_down_when_port_closed(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.assertFalse(warden.probe_server(port, timeout=2))

    def test_apply_user_token_sets_env_when_present(self):
        old_token = os.environ.get("GITHUB_TOKEN")
        old_mapped = os.environ.get("GITHUB__USER_TOKEN")
        os.environ["GITHUB_TOKEN"] = "ghp_demo"
        try:
            self.assertEqual(warden.apply_user_token(), "ghp_demo")
            self.assertEqual(os.environ.get("GITHUB__USER_TOKEN"), "ghp_demo")
        finally:
            if old_token is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = old_token
            if old_mapped is None:
                os.environ.pop("GITHUB__USER_TOKEN", None)
            else:
                os.environ["GITHUB__USER_TOKEN"] = old_mapped

    def test_apply_user_token_without_token_returns_none(self):
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB__USER_TOKEN", None)
        self.assertIsNone(warden.apply_user_token())


if __name__ == "__main__":
    unittest.main()
