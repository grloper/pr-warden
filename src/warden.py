#!/usr/bin/env python3
"""
PR-Warden CLI: review any PR on demand (engine mode), manage the server, and
run Warden's own tooling (insights / digest / badge).

Usage:
  python src/warden.py review <pr-url> [--model local-fast|openai|claude|gemini|custom]
  python src/warden.py describe <pr-url>
  python src/warden.py improve <pr-url>
  python src/warden.py ask <pr-url> "<question>"
  python src/warden.py server             # run the webhook server
  python src/warden.py health             # is the webhook server alive?
  python src/warden.py insights [--days N] [--json]
  python src/warden.py digest   [--days 7]         # markdown to stdout
  python src/warden.py badge    --out badge.svg

CLI (engine) reviews post as your GitHub *user*. Provide a token via
GITHUB_TOKEN (or GITHUB__USER_TOKEN) or rely on PR-Agent's own .secrets.toml.
Every CLI invocation is recorded in the local insights ledger.
"""

import argparse
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
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


def app_config_path() -> Path:
    override = os.environ.get("WARDEN_CONFIG")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "config" / "warden.toml", Path.cwd() / "warden.toml"):
        if candidate.is_file():
            return candidate
    return here.parents[1] / "config" / "warden.toml"


def load_app_config() -> dict:
    path = app_config_path()
    if not path.is_file():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:  # noqa: BLE001 - a broken config must never crash the CLI
        return {}


def resolve_preset(cli: str | None, env: str | None, toml: str | None) -> str:
    return cli or env or toml or "local-fast"


def apply_preset(name: str) -> None:
    env = PRESETS.get(name, PRESETS["local-fast"])
    for k, v in env.items():
        os.environ[k] = v
    os.environ.setdefault("CONFIG__FALLBACK_MODELS", "")
    os.environ.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")
    print(f"[warden] model preset '{name}' -> {os.environ.get('CONFIG__MODEL')}", flush=True)


def apply_user_token() -> str | None:
    """Expose a GitHub user token to the engine for CLI reviews, if available."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB__USER_TOKEN")
    if token:
        os.environ["GITHUB__USER_TOKEN"] = token
        return token
    print(
        "[warden] note: no GITHUB_TOKEN set. CLI reviews post as your GitHub user;\n"
        "          export GITHUB_TOKEN or configure PR-Agent's .secrets.toml.",
        file=sys.stderr,
    )
    return None


def pr_repo(pr_url: str) -> str | None:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/\d+", pr_url)
    return m.group(1) if m else None


def run_engine(cmd: str, pr_url: str, extra: list, model: str) -> int:
    apply_preset(model)
    apply_user_token()
    python = sys.executable
    args = [python, "-m", "pr_agent.cli", f"--pr_url={pr_url}", cmd] + extra
    return subprocess.call(args)


def _run_and_record(cmd: str, pr_url: str, extra: list, model: str) -> int:
    t0 = time.monotonic()
    rc = run_engine(cmd, pr_url, extra, model)
    latency_ms = int((time.monotonic() - t0) * 1000)
    try:
        import insights

        insights.record(
            source="cli", kind=cmd, repo=pr_repo(pr_url), pr=pr_url,
            model=model, rc=rc, latency_ms=latency_ms, detail=" ".join(extra),
        )
    except Exception:  # noqa: BLE001 - recording must never mask a review
        pass
    return rc


def probe_server(port: int, timeout: int = 5) -> bool:
    """A real liveness probe: any HTTP response means the server is up.

    The engine answers unsigned webhook POSTs with 403, which is exactly the
    behaviour we want to detect (signature check alive, server listening).
    """
    url = f"http://127.0.0.1:{port}/api/v1/github_webhooks"
    req = urllib.request.Request(url, data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=timeout).read()
        return True
    except urllib.error.HTTPError:
        return True  # any HTTP response = reachable
    except Exception:  # noqa: BLE001 - connection refused / timeout = down
        return False


def health(port: int) -> int:
    if probe_server(port):
        print(f"[warden] server is UP on :{port} (webhook endpoint responding)")
        return 0
    print(f"[warden] server is DOWN on :{port}", file=sys.stderr)
    return 1


def _print_table(rows, title: str) -> None:
    if not rows:
        print(f"{title}: none yet")
        return
    keys = list(rows[0].keys())
    widths = {k: max(len(str(k)), *(len(str(r[k])) for r in rows)) for k in keys}
    line = "  ".join(str(k).ljust(widths[k]) for k in keys)
    print(f"\n{title}\n{'=' * len(line)}")
    print(line)
    for r in rows:
        print("  ".join(str(r[k]).ljust(widths[k]) for k in keys))


def _insights_lines(s: dict) -> list[str]:
    avg = (f"avg latency    : {s['avg_latency_ms']} ms"
           if s.get("avg_latency_ms") is not None else "avg latency    : n/a")
    return [
        f"total events   : {s['total_events']}  (ok runs: {s['ok_runs']})",
        f"by kind        : {s['by_kind'] or 'none'}",
        f"by repo        : {s['by_repo'] or 'none'}",
        avg,
        f"est CodeRabbit cost: ${s['est_coderabbit_dollars']} (you pay $0)",
    ]


def cmd_insights(args) -> int:
    import insights

    rows = insights.query(since_days=args.days, db=args.db)
    s = insights.summarize(rows)
    if args.json:
        print(insights.json.dumps(s, indent=2))
        return 0
    print("\n".join(_insights_lines(s)))
    return 0


def cmd_digest(args) -> int:
    import insights

    rows = insights.query(since_days=args.days, db=args.db)
    print(insights.digest_markdown(rows, since_days=args.days))
    return 0


def cmd_badge(args) -> int:
    import insights

    rows = insights.query(since_days=args.days, db=args.db)
    svg = insights.badge_svg(insights.summarize(rows))
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"[warden] badge written to {args.out}")
    return 0


def cmd_ask_repo(args) -> int:
    import askrepo

    question = " ".join(args.question)
    print(f"[warden] scanning {args.repo_path} (embed={args.embed_model or 'lexical'})...",
          file=sys.stderr)
    res = askrepo.answer_question(
        question, Path(args.repo_path), top_k=args.top_k,
        model=args.model, embed_model=args.embed_model,
    )
    print(res["answer"])
    if res.get("citations"):
        print("\ncitations:")
        for c in res["citations"]:
            print(f"  {c}")
    return 0


def main() -> int:
    toml = load_app_config()
    default_model = resolve_preset(
        None,
        os.environ.get("WARDEN_PRESET"),
        (toml.get("model") or {}).get("preset"),
    )
    server_port = int(os.environ.get("PORT", (toml.get("server") or {}).get("port", 3000)))

    p = argparse.ArgumentParser(description="PR-Warden CLI")
    p.add_argument("--model", default=None,
                   help="local-fast | local-thinking | openai | claude | gemini | custom")
    sub = p.add_subparsers(dest="cmd", required=True)

    for cmd, help_txt in [("review", "Full PR review"), ("describe", "PR description"),
                          ("improve", "Code suggestions")]:
        sp = sub.add_parser(cmd, help=help_txt)
        sp.add_argument("pr_url")
        sp.add_argument("extra", nargs="*")
        sp.set_defaults(fn=lambda a, c=cmd: _run_and_record(c, a.pr_url, a.extra, a.model or default_model))

    sp = sub.add_parser("ask", help="Ask a question about a PR")
    sp.add_argument("pr_url")
    sp.add_argument("question", nargs="+")
    sp.set_defaults(fn=lambda a: _run_and_record("ask", a.pr_url, [" ".join(a.question)], a.model or default_model))

    sp = sub.add_parser("server", help="Run the webhook server (same as src/run_server.py)")
    sp.set_defaults(fn=lambda a: _server_main())

    sp = sub.add_parser("health", help="Check the webhook server")
    sp.set_defaults(fn=lambda a: health(server_port))

    sp = sub.add_parser("insights", help="Review ledger metrics")
    sp.add_argument("--days", type=int, default=None, help="limit to last N days")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--db", default=None)
    sp.set_defaults(fn=cmd_insights)

    sp = sub.add_parser("digest", help="Weekly digest as markdown (stdout)")
    sp.add_argument("--days", type=int, default=7)
    sp.add_argument("--db", default=None)
    sp.set_defaults(fn=cmd_digest)

    sp = sub.add_parser("badge", help="Write a flat SVG scorecard")
    sp.add_argument("--out", required=True)
    sp.add_argument("--days", type=int, default=None)
    sp.add_argument("--db", default=None)
    sp.set_defaults(fn=cmd_badge)

    sp = sub.add_parser("ask-repo", help="Ask about a local repo (local RAG, offline-capable)")
    sp.add_argument("repo_path")
    sp.add_argument("question", nargs="+")
    sp.add_argument("--top-k", type=int, default=6)
    sp.add_argument("--embed-model", default=os.environ.get("WARDEN_EMBED_MODEL"),
                    help="e.g. nomic-embed-text (default: lexical retrieval)")
    sp.set_defaults(fn=cmd_ask_repo)

    args = p.parse_args()
    return args.fn(args)


def _server_main() -> int:
    import run_server

    run_server.main()
    return 0


def console_entry() -> None:
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
