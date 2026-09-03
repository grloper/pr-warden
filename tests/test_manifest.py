"""Tests for manifest handshake: code exchange, artifact writing, .env updates.

Runs against a local stub of the GitHub app-manifest conversion endpoint.
"""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from manifest import exchange_code, update_env_file, write_artifacts  # noqa: E402

FAKE_CREDS = {
    "name": "pr-warden-test",
    "slug": "pr-warden-test",
    "app_id": 4819001,
    "pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIfake\n-----END RSA PRIVATE KEY-----\n",
    "webhook_secret": "s" * 40,
    "html_url": "https://github.com/apps/pr-warden-test",
}


class Stub(BaseHTTPRequestHandler):
    status = 200
    body = json.dumps(FAKE_CREDS).encode()
    seen_auth = None

    def log_message(self, *a):
        pass

    def do_POST(self):
        Stub.seen_auth = self.headers.get("Authorization")
        self.send_response(Stub.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(Stub.body)


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_exchange_returns_credentials(self):
        data = exchange_code("code123", api_base=self.base)
        self.assertEqual(data["name"], "pr-warden-test")
        self.assertEqual(data["app_id"], 4819001)

    def test_exchange_sends_bearer_when_token_given(self):
        Stub.seen_auth = None
        exchange_code("code124", api_base=self.base, token="ghp_secret")
        self.assertEqual(Stub.seen_auth, "Bearer ghp_secret")

    def test_exchange_raises_on_http_error(self):
        Stub.status, Stub.body = 500, b'{"message":"boom"}'
        try:
            with self.assertRaises(RuntimeError) as ctx:
                exchange_code("bad", api_base=self.base)
            self.assertIn("500", str(ctx.exception))
        finally:
            Stub.status, Stub.body = 200, json.dumps(FAKE_CREDS).encode()

    def test_write_artifacts_persists_pem_and_json(self, tmp=None):
        out = Path(self._mk_tmp()) if tmp is None else tmp
        write_artifacts(out, FAKE_CREDS)
        self.assertTrue((out / "app.json").is_file())
        pem = (out / "pr-warden.pem").read_text(encoding="ascii")
        self.assertIn("BEGIN RSA PRIVATE KEY", pem)

    def test_update_env_file_replaces_and_appends(self):
        env = Path(self._mk_tmp()) / ".env"
        env.write_text("GITHUB_APP_ID=old\nPORT=3000\n", encoding="utf-8")
        changed = update_env_file(env, {"GITHUB_APP_ID": "4819001", "WEBHOOK_SECRET": "zz"})
        text = env.read_text(encoding="utf-8")
        self.assertIn("GITHUB_APP_ID=4819001", text)
        self.assertIn("WEBHOOK_SECRET=zz", text)
        self.assertIn("PORT=3000", text)
        self.assertEqual(len(changed), 2)

    @staticmethod
    def _mk_tmp():
        import tempfile

        d = tempfile.mkdtemp(prefix="warden-test-")
        return d


if __name__ == "__main__":
    unittest.main()
