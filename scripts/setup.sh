#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# PR-Warden one-shot setup — macOS / Linux
# 1. reads .env, 2. registers GitHub App (manifest flow),
# 3. starts tunnel + server, 4. installs autostart (launchd/systemd)
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== PR-Warden setup ==="

# 1. Python venv + engine
if [ ! -d ".venv" ]; then
  echo "[*] Creating venv..."
  python3 -m venv .venv
fi
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q "pr-agent"

# 2. Load .env if present
if [ -f ".env" ]; then set -a; source .env; set +a; fi

# 3. Ensure config
[ -f "config/warden.toml" ] || cp config/warden.toml.example config/warden.toml

# 4. Tunnel: tailscale funnel preferred
TUNNEL_PROVIDER="${TUNNEL_PROVIDER:-tailscale-funnel}"
BASE_URL="http://127.0.0.1:${PORT:-3000}"
if [ "$TUNNEL_PROVIDER" = "tailscale-funnel" ] && command -v tailscale >/dev/null; then
  echo "[*] Enabling Tailscale Funnel on :${PORT:-3000}..."
  tailscale funnel --bg "${PORT:-3000}" >/dev/null || echo "    (funnel may need one-time admin enable — see docs)"
  HOST=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null || true)
  BASE_URL="https://${HOST}"
elif [ "$TUNNEL_PROVIDER" = "ngrok" ] && command -v ngrok >/dev/null; then
  echo "[*] Starting ngrok..."
  (ngrok http "${PORT:-3000}" >/dev/null 2>&1 &)
fi
echo "[*] Public base URL will be: ${BASE_URL}"

# 5. Generate manifest and print registration instructions
echo "[*] Generating GitHub App manifest..."
./.venv/bin/python src/manifest.py create --base-url "$BASE_URL" --name "${GITHUB_APP_NAME:-pr-warden}"

echo
echo "NEXT STEPS (one browser click each):"
echo "  1. Register the app from the manifest (see src/manifest.py create output)."
echo "  2. Start the capture server:  ./.venv/bin/python src/manifest.py capture"
echo "  3. Run the warden server:     ./.venv/bin/python src/run_server.py"
echo "  4. Install the app on your repos and open a test PR."
