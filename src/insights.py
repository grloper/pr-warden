"""
PR-Warden Insights: a local, zero-dependency review ledger.

Records every review/command/webhook delivery in SQLite under
~/.pr-warden/warden.db (or $WARDEN_STATE_DIR), then summarises it:

  warden insights [--days N] [--json]     metrics table
  warden digest   [--days 7]              weekly markdown digest (stdout)
  warden badge    --out badge.svg         flat SVG scorecard

Nothing leaves the machine. No engine hooks required: the CLI records its own
invocations and the webhook server records deliveries via ASGI middleware.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,            -- cli | server
    kind TEXT NOT NULL,              -- review | describe | improve | ask | webhook
    repo TEXT,
    pr TEXT,
    model TEXT,
    rc INTEGER,
    latency_ms INTEGER,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);
"""


def state_dir() -> Path:
    return Path(os.environ.get("WARDEN_STATE_DIR", Path.home() / ".pr-warden"))


def default_db() -> Path:
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "warden.db"


def _connect(db=None) -> sqlite3.Connection:
    path = Path(db) if db else default_db()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con


def record(source: str, kind: str, repo=None, pr=None, model=None,
           rc=None, latency_ms=None, detail=None, db=None) -> None:
    con = _connect(db)
    try:
        con.execute(
            "INSERT INTO events (ts, source, kind, repo, pr, model, rc, latency_ms, detail)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), source, kind, repo, pr, model,
             rc, latency_ms, detail),
        )
        con.commit()
    finally:
        con.close()


def query(since_days: int | None = None, db=None) -> list[dict]:
    con = _connect(db)
    try:
        sql = "SELECT * FROM events"
        args: tuple = ()
        if since_days is not None:
            sql += " WHERE ts >= datetime('now', ?)"
            args = (f"-{int(since_days)} days",)
        rows = con.execute(sql + " ORDER BY id", args).fetchall()
        cols = [c[0] for c in con.execute("SELECT * FROM events LIMIT 0").description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()


def summarize(rows: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    repos: dict[str, int] = {}
    lat = []
    total = len(rows)
    ok = 0
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        if r.get("repo"):
            repos[r["repo"]] = repos.get(r["repo"], 0) + 1
        if r.get("latency_ms") is not None:
            lat.append(int(r["latency_ms"]))
        if r.get("rc") == 0:
            ok += 1
    return {
        "total_events": total,
        "by_kind": kinds,
        "by_repo": dict(sorted(repos.items(), key=lambda kv: -kv[1])),
        "ok_runs": ok,
        "avg_latency_ms": int(sum(lat) / len(lat)) if lat else None,
        "max_latency_ms": max(lat) if lat else None,
        # rough public-market comparison: CodeRabbit Lite is $12/mo for ~500 PRs
        "est_coderabbit_dollars": round(total * 0.024, 2),
    }


def digest_markdown(rows: list[dict], since_days: int = 7, db=None) -> str:
    s = summarize(rows)
    lines = [
        f"# PR-Warden weekly digest (last {since_days} days)",
        "",
        f"- **Events recorded:** {s['total_events']}",
        f"- **Breakdown:** " + ", ".join(f"{k}={v}" for k, v in s["by_kind"].items()) or "none",
        f"- **Repos:** " + ", ".join(f"{k} ({v})" for k, v in s["by_repo"].items()) or "none",
        f"- **Avg webhook latency:** {s['avg_latency_ms']} ms" if s["avg_latency_ms"] is not None else "- Avg latency: n/a",
        f"- **Est. equivalent CodeRabbit cost:** ${s['est_coderabbit_dollars']:.2f} (you pay $0)",
        "",
    ]
    return "\n".join(lines)


def badge_svg(summary: dict, label: str = "PR-Warden") -> str:
    value = f"{summary['total_events']} events"
    if summary.get("by_kind", {}).get("review"):
        value = f"{summary['by_kind']['review']} reviews"
    lw, vw = 92, 24 + len(value) * 7
    color = "#3fb950" if summary["ok_runs"] >= summary["total_events"] * 0.8 or not summary["total_events"] else "#d29922"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{lw + vw}" height="20" role="img">
  <title>{label}</title>
  <rect width="{lw}" height="20" fill="#0d1424"/>
  <rect x="{lw}" width="{vw}" height="20" fill="{color}"/>
  <text x="6" y="14" fill="#fff" font-family="Segoe UI, sans-serif" font-size="11">{label}</text>
  <text x="{lw + 6}" y="14" fill="#fff" font-family="Segoe UI, sans-serif" font-size="11">{value}</text>
</svg>'''


if __name__ == "__main__":
    print(json.dumps(summarize(query()), indent=2))
