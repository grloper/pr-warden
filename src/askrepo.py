"""
PR-Warden "Ask your codebase" - fully local repo Q&A.

  warden ask-repo <repo_path> "<question>" [--top-k N] [--embed-model nomic-embed-text]

How it works:
  1. Text files are chunked into overlapping windows (path + line ranges).
  2. Retrieval is lexical by default (zero deps); if Ollama is reachable and
     WARDEN_EMBED_MODEL is set it upgrades to embedding cosine similarity.
  3. Top chunks are assembled into a prompt answered by the local model
     (qwen2.5-coder:14b by default) with file:line citations.

No code leaves the machine.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build",
             "dist", ".idea", ".vscode", ".tox", "htmlcov", ".pytest_cache"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
              ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot", ".pem", ".key",
              ".db", ".sqlite", ".pyc", ".lock"}
TEXT_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
            ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".sh",
            ".ps1", ".md", ".rst", ".txt", ".toml", ".yaml", ".yml", ".json",
            ".html", ".css", ".scss", ".sql", ".dockerfile", ".ini", ".cfg"}


@dataclass
class Chunk:
    path: str
    start: int
    text: str
    _tokens: list[str] = field(default_factory=list, repr=False)

    def tokens(self) -> list[str]:
        if not self._tokens:
            self._tokens = _tokenize(self.text)
        return self._tokens

    def cite(self) -> str:
        return f"{self.path}:{self.start}"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def iter_chunks(root: Path, window: int = 80, overlap: int = 10,
                max_files: int = 800, max_bytes: int = 1_500_000) -> list[Chunk]:
    """Window text files into overlapping chunks with line numbers."""
    chunks: list[Chunk] = []
    root = root.resolve()
    cap_factor = (window // overlap + 2) if overlap else (window + 2)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or len(chunks) >= max_files * cap_factor:
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in BINARY_EXT:
            continue
        if path.suffix.lower() not in TEXT_EXT and path.name.lower() not in (
                "dockerfile", "makefile", "license", "readme", "contributing"):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:  # noqa: BLE001
            continue
        step = max(window - overlap, 1)
        for start in range(0, max(len(lines), 1), step):
            end = min(start + window, len(lines))
            if not lines and start == 0:
                body = ""
            else:
                body = "\n".join(lines[start:end])
            if body.strip():
                chunks.append(Chunk(rel.as_posix(), start + 1, body))
        if len(chunks) >= max_files * 40:
            break
    return chunks


def lexical_retrieve(query: str, chunks: list[Chunk], top_k: int = 5) -> list[tuple[float, Chunk]]:
    """Simple ranked retrieval: term overlap weighted by corpus rarity."""
    q = _tokenize(query)
    if not q or not chunks:
        return []
    n = len(chunks)
    df = {}
    for c in chunks:
        for t in set(c.tokens()):
            df[t] = df.get(t, 0) + 1
    scored = []
    for c in chunks:
        ct = c.tokens()
        if not ct:
            continue
        freq = {}
        for t in ct:
            freq[t] = freq.get(t, 0) + 1
        score = 0.0
        for t in q:
            if t in freq:
                idf = math.log((n + 1) / (df.get(t, 0) + 1)) + 1.0
                score += idf * (1 + math.log(freq[t]))
        if score > 0:
            # slight length normalisation
            scored.append((score / (1 + math.log(len(ct))), c))
    scored.sort(key=lambda pair: -pair[0])
    return scored[:top_k]


def _ollama_embed(texts: list[str], model: str, base: str) -> list[list[float]] | None:
    import json
    import urllib.error
    import urllib.request

    out = []
    try:
        for t in texts:
            body = json.dumps({"model": model, "prompt": t[:8000]}).encode()
            req = urllib.request.Request(f"{base.rstrip('/')}/api/embeddings",
                                         data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=60) as r:
                vec = json.loads(r.read().decode())["embedding"]
            out.append(vec)
        return out
    except Exception:  # noqa: BLE001 - fall back to lexical
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def embed_retrieve(query: str, chunks: list[Chunk], model: str,
                   base: str, top_k: int = 5) -> list[tuple[float, Chunk]]:
    vecs = _ollama_embed([c.text[:2000] for c in chunks], model, base)
    qv = _ollama_embed([query], model, base)
    if not vecs or not qv:
        return []
    scored = [(float(_cosine(qv[0], v)), c) for v, c in zip(vecs, chunks)]
    scored.sort(key=lambda pair: -pair[0])
    return scored[:top_k]


def retrieve_top(query: str, chunks: list[Chunk], top_k: int = 5,
                 embed: bool = True, embed_model: str | None = None,
                 ollama_base: str | None = None) -> list[tuple[float, Chunk]]:
    if embed and embed_model:
        hits = embed_retrieve(query, chunks, embed_model,
                              ollama_base or os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434"),
                              top_k)
        if hits:
            return hits
    return lexical_retrieve(query, chunks, top_k)


def build_prompt(question: str, hits: list[tuple[float, Chunk]], repo_name: str) -> str:
    context = []
    for score, c in hits:
        context.append(f"--- {c.cite()} (score {score:.3f}) ---\n{c.text}")
    context_block = "\n\n".join(context) if context else "(no matching code found)"
    return (
        f"You are an expert on the {repo_name} codebase. Answer concisely using "
        "only the provided context. Cite file:line for every claim.\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"QUESTION: {question}\n\nANSWER:"
    )


def chat(prompt: str, model: str, base: str, timeout: int = 300) -> str:
    import json
    import urllib.request

    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "stream": False}).encode()
    req = urllib.request.Request(f"{base.rstrip('/')}/api/chat", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["message"]["content"]


def answer_question(question: str, repo_path: Path, top_k: int = 6,
                    model: str | None = None, embed_model: str | None = None,
                    ollama_base: str | None = None) -> dict:
    ollama_base = ollama_base or os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434")
    model = model or os.environ.get("WARDEN_MODEL", "ollama/qwen2.5-coder:14b").split("/")[-1]
    repo_path = Path(repo_path)
    chunks = iter_chunks(repo_path)
    hits = retrieve_top(question, chunks, top_k, embed_model=embed_model,
                        ollama_base=ollama_base)
    prompt = build_prompt(question, hits, repo_path.name)
    try:
        answer = chat(prompt, model, ollama_base)
    except Exception as e:  # noqa: BLE001
        answer = f"(local model unavailable: {e})"
    citations = [c.cite() for _, c in hits]
    return {"question": question, "answer": answer,
            "citations": citations, "chunks_scanned": len(chunks)}
