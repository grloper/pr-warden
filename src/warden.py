#!/usr/bin/env python3
"""
PR-Warden CLI: review any PR on demand (engine mode) or manage the server.

Usage:
  python src/warden.py review <pr-url> [--model local-fast|openai|claude|gemini|custom]
  python src/warden.py server            # run webhook server (same as run_server.py)
  python src/warden.py describe <pr-url>
  python src/warden.py ask <pr-url> "<question>"
  python src/warden.py health            # check local server
"""

import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PRESETS = {
    "local-fast": {"CONFIG__MODEL": "ollama/qwen2.5-coder:14b", "CONFIG__CUSTOM_MODEL_MAX_TOKENS": "32000"},
    "local-thinking": {"CONFIG__MODEL": "ollama/hf.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF:Q4_K_M", "CONFIG__CUSTOM_MODEL_MAX_TOKENS": "131072"},
    "openai": {"CONFIG__MODEL": os.environ.get("WARDEN_MODEL", "gpt-4o")},
    "claude": {"CONFIG__MODEL": os.environ.get("WARDEN_MODEL", "anthropic/claude-sonnet-4")},
    "gemini": {"CONFIG__MODEL": os.environ.get("WARDEN_MODEL", "gemini/gemini-2.0-flash")},
    "custom": {"CONFIG__MODEL": os.environ.get("WARDEN_MODEL", "")},
}


def apply_preset(name: str) -> None:
    env = PRESETS.get(name, PRESETS["local-fast"])
    for k, v in env.items():
        os.environ[k] = v
    os.environ.setdefault("CONFIG__FALLBACK_MODELS", "")
    os.environ.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")
    print(f"[warden] model preset '{name}' -> {os.environ.get('CONFIG__MODEL')}", flush=True)


def run_engine(cmd: str, pr_url: str, extra: list, model: str) -> int:
    apply_preset(model)
    os.environ.setdefault("GITHUB_TOKEN", "")
    python = sys.executable
    args = [python, "-m", "pr_agent.cli", f"--pr_url={pr_url}", cmd] + extra
    return subprocess.call(args)


def health(port: int = 3000) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            print(r.read().decode())
            return 0
    except Exception as e:
        print(f"[warden] server not responding: {e}", file=sys.stderr)
        return 1


def main() -> int:
    p = argparse.ArgumentParser(description="PR-Warden CLI")
    p.add_argument("--model", default=os.environ.get("WARDEN_PRESET", "local-fast"),
                   help="local-fast | local-thinking | openai | claude | gemini | custom")
    sub = p.add_subparsers(dest="cmd", required=True)

    for cmd, help_txt in [("review", "Full PR review"), ("describe", "PR description"),
                          ("improve", "Code suggestions")]:
        sp = sub.add_parser(cmd, help=help_txt)
        sp.add_argument("pr_url")
        sp.add_argument("extra", nargs="*")
        sp.set_defaults(fn=lambda a, c=cmd: run_engine(c, a.pr_url, a.extra, a.model))

    sp = sub.add_parser("ask", help="Ask a question about a PR")
    sp.add_argument("pr_url")
    sp.add_argument("question", nargs="+")
    sp.set_defaults(fn=lambda a: run_engine("ask", a.pr_url, [" ".join(a.question)], a.model))

    sp = sub.add_parser("health", help="Check the webhook server")
    sp.set_defaults(fn=lambda a: health())

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
