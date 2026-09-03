# 🛡️ PR-Warden

**Your private, always-on AI code reviewer — self-hosted, model-agnostic, zero per-review cost.**

PR-Warden is a production-grade, fully self-hosted pull-request review system built
on the battle-tested [PR-Agent](https://github.com/The-PR-Agent/pr-agent) engine
and wrapped with everything you need to run it as **your own GitHub App** in
minutes — no cloud LLM bills, no third-party review SaaS, no code leaving your
machine (unless *you* choose a cloud model).

It reviews every PR on every repo you install it on, posts structured reviews,
catches real bugs, and answers your `/review`, `/improve`, and `/ask` commands —
like CodeRabbit, but **owned by you**.

---

## ✨ Why PR-Warden?

| | CodeRabbit | PR-Agent (raw) | **PR-Warden** |
|---|---|---|---|
| Self-hosted / you own it | ❌ SaaS | ✅ | ✅ |
| Runs 100% on your GPU (Ollama) | ❌ | manual | ✅ one command |
| Zero per-review cost | ❌ $$$ | ✅ | ✅ |
| One-command GitHub App setup | — | multi-step | ✅ manifest + script |
| Model presets (local **and** cloud) | partial | manual config | ✅ `--model` presets |
| Public stable webhook URL (Tailscale Funnel) | — | manual | ✅ scripted |
| Survives reboots | — | manual | ✅ installs auto-start |
| Multi-git-host (GitHub/GitLab/Bitbucket/… via engine) | GitHub only | ✅ | ✅ |
| Clean brandable name + docs | — | — | ✅ |

PR-Warden doesn't reinvent the AI-review engine — it makes the **full stack
around it trivial**: GitHub App registration, tunnel, autostart, model
switching, and multi-repo installation. You get the industry's best open
reviewer with an operator-friendly, opinionated wrapper.

---

## 🧱 Architecture

```
                 ┌────────────────────────────────────────────┐
  GitHub         │  Your machine                               │
  (PR opened)    │                                            │
     │           │   ┌──────────────┐      ┌───────────────┐  │
     └──────────▶│   │  Webhook     │ ───▶ │ PR-Warden     │  │
   webhook       │   │  (Tailscale  │      │ server        │  │
                 │   │   Funnel /   │      │ (PR-Agent)    │  │
                 │   │   ngrok)     │      │   :3000       │  │
                 │   └──────────────┘      └──────┬────────┘  │
                 │                                │           │
                 │                     ┌──────────▼────────┐  │
                 │                     │  Model backend    │  │
                 │                     │  Ollama (local)   │  │
                 │                     │  or any LiteLLM   │  │
                 │                     │  provider (cloud) │  │
                 │                     └───────────────────┘  │
                 └────────────────────────────────────────────┘
```

**Flow:** open (or update) a PR → GitHub sends a webhook to your machine →
PR-Warden authenticates as your GitHub App → the model reviews the diff →
structured review + code suggestions + labels are posted back as the bot.

---

## 🚀 Quick start (10 minutes)

### Prereqs
- Docker **or** Python 3.11+ (your choice of runtime)
- [Ollama](https://ollama.com) with a model: `ollama pull qwen2.5-coder:14b`
- A GitHub account

### 1. Configure
```bash
cp .env.example .env          # set GITHUB_APP_ID / WEBHOOK_SECRET later
cp config/warden.toml.example config/warden.toml
```

### 2. Run the one-shot installer
```bash
./scripts/setup.sh                 # macOS / Linux
# or
.\scripts\setup.ps1                # Windows
```
The installer:
1. Generates a **GitHub App manifest** (branded, minimal permissions).
2. Opens the one-time registration page (paste-friendly).
3. Exchanges the redirect code → saves your app ID + private key into `.secrets/` (gitignored).
4. Starts the server + tunnel + autostart task.

### 3. Install the App on your repos
Click the returned install link, choose **All repositories**, done.

Open a test PR — the bot reviews it automatically. 🎉

---

## 🧠 Model presets

Bring any model: local or cloud, one flag.

| Preset | Backend | Command |
|---|---|---|
| `local-fast` | Ollama `qwen2.5-coder:14b` | `--model local-fast` |
| `local-thinking` | Ollama Qwythos/other GGUF | `--model local-thinking` |
| `openai` | OpenAI GPT | `--model openai` |
| `claude` | Anthropic Claude | `--model claude` |
| `gemini` | Google Gemini | `--model gemini` |
| `custom` | Any LiteLLM provider | set `WARDEN_MODEL` |

Cloud presets only need an API key in `.env` — no code changes.

---

## 🎛️ Runtime options

- **Webhook mode** (default): always-on GitHub App, auto-reviews every PR.
- **CLI mode**: review on demand — `warden review <pr-url>`.
- **Action mode**: GitHub Action per repo (no server needed; cloud model).

---

## 🔒 Security & privacy

- Private key never leaves `.secrets/` (gitignored).
- Webhook signature verified against your secret on every request.
- Local mode: **your code never leaves your machine**.
- App scoped to least privilege: read contents/metadata, write issues/PRs.

---

## 📜 License

MIT — do anything, fork it, brand it, run it for your team. Attribution
appreciated but not required. PR-Agent (engine) remains MIT-licensed upstream.

---

*PR-Warden: review everything. Own everything.*
