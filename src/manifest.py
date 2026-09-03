#!/usr/bin/env python3
"""
PR-Warden GitHub App manifest generator.

Creates a minimal-permission GitHub App manifest and prints the one-time
registration URL. After you click "Create GitHub App" in the browser, GitHub
redirects to your local capture endpoint with a code; this script's companion
(capture mode) exchanges it for your App ID + private key + webhook secret.

Usage:
  python src/manifest.py create                  # print manifest + register URL
  python src/manifest.py capture --port 3000     # receive redirect, exchange code

No API keys required: the manifest flow uses GitHub's public handshake.
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MANIFEST = {
    "name": "pr-warden",
    "url": "https://github.com",
    "description": "Self-hosted AI PR reviewer (PR-Warden) running on your own machine.",
    "public": False,
    "default_permissions": {
        "actions": "read",
        "checks": "write",
        "contents": "read",
        "issues": "write",
        "metadata": "read",
        "pull_requests": "write",
        "statuses": "read",
    },
    "default_events": [
        "pull_request",
        "pull_request_review",
        "pull_request_review_comment",
        "issue_comment",
        "push",
    ],
    "request_oauth_on_install": False,
}


def build_manifest(base_url: str, app_name: str) -> dict:
    manifest = dict(DEFAULT_MANIFEST)
    manifest["name"] = app_name
    manifest["hook_attributes"] = {
        "url": f"{base_url}/api/v1/github_webhooks",
        "active": True,
    }
    manifest["redirect_url"] = f"{base_url}/manifest_capture"
    return manifest


def cmd_create(args) -> int:
    app_name = args.name
    base_url = args.base_url or "http://127.0.0.1:3000"
    manifest = build_manifest(base_url, app_name)

    out = Path(args.out)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[*] Manifest written to {out}")
    print(f"[*] Webhook URL : {manifest['hook_attributes']['url']}")
    print(f"[*] Redirect URL: {manifest['redirect_url']}")
    print()
    print("To register:")
    print("  1. Serve this file (or any page that POSTs it as the 'manifest' form field)")
    print("     to https://github.com/settings/apps/new  (personal account)")
    print("  2. Click 'Create GitHub App', GitHub redirects to your redirect_url")
    print("     with ?code=... — run 'capture' to finish the handshake.")
    return 0


def cmd_capture(args) -> int:
    import http.server
    import urllib.parse

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    code_file = out_dir / "manifest_code.txt"

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, body: bytes, ctype: str = "text/html") -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/manifest.json":
                mf = Path(args.manifest)
                self._send(mf.read_bytes() if mf.exists() else b"{}", "application/json")
                return
            code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
            if code:
                code_file.write_text(code, encoding="utf-8")
                print(f"[*] Captured manifest code -> {code_file}", flush=True)
                self._send(b"<h1>Code captured - you can close this tab.</h1>")
            else:
                self._send(b"<h1>Warden capture server ready.</h1>")

    port = args.port
    print(f"[*] Listening on :{port} — waiting for GitHub redirect...", flush=True)
    http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PR-Warden GitHub App manifest tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Generate the app manifest")
    p_create.add_argument("--name", default="pr-warden")
    p_create.add_argument("--base-url", default=None, help="Public tunnel URL, e.g. https://host.ts.net")
    p_create.add_argument("--out", default="manifests/warden-manifest.json")
    p_create.set_defaults(func=cmd_create)

    p_cap = sub.add_parser("capture", help="Receive the manifest redirect and exchange the code")
    p_cap.add_argument("--port", type=int, default=3000)
    p_cap.add_argument("--out-dir", default=".secrets")
    p_cap.add_argument("--manifest", default="manifests/warden-manifest.json")
    p_cap.set_defaults(func=cmd_capture)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
