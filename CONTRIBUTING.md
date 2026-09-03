# Contributing to PR-Warden

Thanks for helping make PR-Warden better! Every PR opened here is
automatically reviewed by PR-Warden itself (dogfooding) — so the bot may
comment before a human does. That's a feature, not a bug. 🛡️

## Quick start

```bash
# Fork + clone, then:
cp .env.example .env
python3 -m venv .venv && ./.venv/bin/pip install -e .[dev]  # or use scripts/setup.sh
python src/manifest.py create --base-url http://127.0.0.1:3000
```

## Development workflow

1. Create a branch: `git checkout -b feat/my-change`
2. Make focused changes with tests where practical.
3. Run the syntax gate before pushing:
   ```bash
   python -m py_compile src/*.py
   ```
4. Open a PR against `main`. PR-Warden's bot will auto-review it.

## What we look for

- **Correctness** — does it work, including the Windows path?
- **No secrets** — never commit `.env`, `.secrets/`, `*.pem`.
- **Portability** — keep scripts ASCII-safe and cross-platform where possible.
- **Docs** — update README or docs/ when behavior changes.

## Commit conventions

`feat:`, `fix:`, `docs:`, `chore:`, `refactor:` prefix, imperative mood,
concise subject line.

## Questions?

Open an issue — the maintainers (and the bot) will get back to you.
