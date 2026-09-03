# Changelog

## 0.2.0 - 2026-09-03

Big "make it real" release: one-shot setup, honest CLI, packaging + CI,
local insights, and offline repo Q&A.

### Added
- **One-shot App handshake**: `warden-manifest capture` now exchanges the
  manifest code itself and writes App credentials into `.secrets/` + `.env`
  (no more manual exchange step).
- **Insights ledger** (`~/.pr-warden/warden.db`): records every CLI run and
  every webhook delivery locally. New commands: `warden insights`,
  `warden digest`, `warden badge --out badge.svg`.
- **Ask your codebase**: `warden ask-repo <path> "question"` - offline-capable
  repo Q&A with file:line citations (lexical by default, optional
  `nomic-embed-text` embeddings via Ollama).
- **Packaging**: `pyproject.toml` + console scripts (`warden`,
  `warden-server`, `warden-manifest`, `warden-validate`).
- **CI**: unit tests on Python 3.11/3.12/3.13, syntax gate, CLI + config
  smoke tests.
- **Per-repo tuning**: `.pr_agent.toml.example` template.
- **Docker**: image now ships the full `src/` (insights recorder ready).

### Fixed
- Action-mode workflow pulled a private GHCR image (`ghcr.io/the-pr-agent/...`)
  that GitHub denies; now uses the public `codiumai/pr-agent:github_action`
  and is opt-in via `WARDEN_ACTION=true`.
- CLI mode hinted at a missing `GITHUB_TOKEN` instead of failing cryptically;
  `warden health` now does a real liveness probe.
- `.env.example` / `.gitignore` mojibake cleaned; `config/warden.toml.example`
  now reflects what actually reads it; `CONTRIBUTING` quick start installable.
- `manifest create` warns when the GitHub App name is globally taken.

### Tests
26 unit tests (`python -m unittest discover -s tests`).
