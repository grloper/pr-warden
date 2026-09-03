#!/usr/bin/env python3
"""
PR-Warden GitHub App manifest generator + one-shot handshake finisher.

Create -> register in the browser -> capture. `capture` no longer stops at the
redirect code: it exchanges the code for your App ID, private key and webhook
secret (GitHub's public app-manifest conversion endpoint), writes them into
.secrets/, and fills .env — the setup is finished in one step.

Usage:
  python src/manifest.py create --base-url https://host.ts.net [--name my-warden]
  python src/manifest.py capture --port 3000 [--token ghp_...] [--api-base https://api.github.com]

The exchange endpoint is authenticated by the one-time code itself; pass
--token only if your API returns 401/403.
"""

import argparse
import http.server
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_MANIFEST = {
    "url": "https://github.com",
    "description": (
        "Self-hosted AI PR reviewer (PR-Warden) running on your own machine. "
        "Reviews every PR on installed repos."
    ),
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


def exchange_code(code: str, api_base: str = "https://api.github.com",
                  token: str | None = None) -> dict:
    """Exchange the one-time manifest code for App credentials (public flow)."""
    url = f"{api_base.rstrip('/')}/app-manifests/{code.strip()}/conversions"
    req = urllib.request.Request(url, method="POST", data=b"")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2026-03-10")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"conversion failed HTTP {e.code}: {detail}") from e


def write_artifacts(out_dir: Path, data: dict, pem_name: str = "pr-warden.pem") -> None:
    """Persist app credentials. Never prints secrets."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "app.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    pem = data.get("pem", "")
    if pem:
        if not pem.endswith("\n"):
            pem += "\n"
        (out_dir / pem_name).write_text(pem, encoding="ascii")
    summary = {
        "name": data.get("name"),
        "slug": data.get("slug"),
        "app_id": data.get("app_id") or data.get("id"),
        "html_url": data.get("html_url"),
        "pem_written": bool(pem),
        "webhook_secret_written": bool(data.get("webhook_secret")),
    }
    print(f"[*] App credentials saved under {out_dir}")
    print(f"[*] {json.dumps(summary, indent=2)}")


def update_env_file(path: Path, updates: dict) -> list[str]:
    """Set KEY=VALUE lines in a .env-style file, preserving the rest."""
    changed = []
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    for key, value in updates.items():
        marker = f"{key}="
        found = False
        for i, line in enumerate(lines):
            if line.startswith(marker):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        changed.append(f"{key} updated")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def cmd_create(args) -> int:
    manifest = build_manifest(args.base_url or "http://127.0.0.1:3000", args.name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[*] Manifest written to {out}")
    print(f"[*] Webhook URL : {manifest['hook_attributes']['url']}")
    print(f"[*] Redirect URL: {manifest['redirect_url']}")
    print()
    print("To register:")
    print("  1. Open a page that POSTs this manifest to github.com/settings/apps/new")
    print("     (or register it via the GitHub UI) and click 'Create GitHub App'.")
    print("  2. GitHub redirects to your redirect_url with ?code=... — run 'capture'.")
    print()
    print("Note: GitHub App names are unique. If GitHub says the name is already")
    print("taken, re-run with a unique name, e.g. --name pr-warden-<your-handle>.")
    return 0


def cmd_capture(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    code_file = out_dir / "manifest_code.txt"
    env_path = Path(args.env)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
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
            if not code:
                self._send(b"<h1>Warden capture server ready.</h1>")
                return
            code_file.write_text(code, encoding="utf-8")
            print(f"[*] Captured manifest code -> {code_file}", flush=True)
            try:
                data = exchange_code(code, args.api_base, token=args.token)
                write_artifacts(out_dir, data)
                changed = update_env_file(
                    env_path,
                    {
                        "GITHUB_APP_ID": str(data.get("app_id") or data.get("id") or ""),
                        "WEBHOOK_SECRET": str(data.get("webhook_secret") or ""),
                        "GITHUB_APP_NAME": str(data.get("name") or ""),
                    },
                )
                print(f"[*] .env {changed}")
                body = (
                    f"<h2>Registered {data.get('name')} (id={data.get('app_id') or data.get('id')})</h2>"
                    "<p>Credentials saved under .secrets/. "
                    "You can close this tab and start the server.</p>"
                )
                self._send(body.encode("utf-8"))
            except Exception as e:  # noqa: BLE001 - report and keep listening
                print(f"[!] exchange failed: {e}", flush=True)
                self._send(f"<h2>Exchange failed</h2><pre>{e}</pre>".encode("utf-8"))

    port = args.port
    print(f"[*] Listening on :{port} - waiting for GitHub redirect...", flush=True)
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

    p_cap = sub.add_parser("capture", help="Receive the redirect, exchange the code, save credentials")
    p_cap.add_argument("--port", type=int, default=3000)
    p_cap.add_argument("--out-dir", default=".secrets")
    p_cap.add_argument("--manifest", default="manifests/warden-manifest.json")
    p_cap.add_argument("--token", default=None, help="Optional user token for the exchange call")
    p_cap.add_argument("--api-base", default="https://api.github.com")
    p_cap.add_argument("--env", default=".env")
    p_cap.set_defaults(func=cmd_capture)

    args = parser.parse_args()
    return args.func(args)


def console_entry() -> None:
    sys.exit(main())


if __name__ == "__main__":
    main()
