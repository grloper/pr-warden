"""
PR-Warden server launcher.

Runs the PR-Agent github_app webhook server with Warden's env-driven config.
This mirrors the exact production configuration proven end-to-end:
  - deployment_type = "app" (GitHub App installation tokens)
  - app_id forced to *string* (PyGithub puts it in the JWT "iss" claim,
    which PyJWT requires as a string — dynaconf coerces numeric env to int)
  - UTF-8 forced so loguru doesn't crash on emoji in non-UTF8 consoles
"""

import json
import os

# Must be set before any pr_agent import.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

# Defaults mirroring config/warden.toml.example
os.environ.setdefault("PORT", "3000")
os.environ.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")
os.environ.setdefault("CONFIG__MODEL", "ollama/qwen2.5-coder:14b")
os.environ.setdefault("CONFIG__FALLBACK_MODELS", "")
os.environ.setdefault("CONFIG__CUSTOM_MODEL_MAX_TOKENS", "32000")
os.environ.setdefault("GITHUB__DEPLOYMENT_TYPE", "app")
os.environ.setdefault("GITHUB_APP__OVERRIDE_DEPLOYMENT_TYPE", "true")


def _read_private_key() -> str:
    """Resolve the app private key from env or the conventional .secrets path."""
    env_key = os.environ.get("GITHUB__PRIVATE_KEY") or os.environ.get("GITHUB_APP_PRIVATE_KEY")
    if env_key:
        # Accept either raw PEM content or a file path.
        if "BEGIN" in env_key:
            return env_key
        path = os.path.expanduser(env_key)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    # Conventional location: .secrets/pr-warden.pem (repo root) or ~/.pr-warden.pem
    for candidate in (
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".secrets", "pr-warden.pem"),
        os.path.expanduser("~/.pr-warden.pem"),
        os.path.expanduser("~/.pr-agent/pr-agent.pem"),
    ):
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return f.read()
    raise RuntimeError(
        "No GitHub App private key found. Set GITHUB__PRIVATE_KEY or place "
        "the PEM at .secrets/pr-warden.pem"
    )


def main() -> None:
    from pr_agent.config_loader import get_settings

    settings = get_settings()

    # Enforce deployment as a GitHub App.
    settings.set("GITHUB.DEPLOYMENT_TYPE", "app")
    settings.set("GITHUB_APP.OVERRIDE_DEPLOYMENT_TYPE", True)
    settings.set("GITHUB.APP_NAME", os.environ.get("GITHUB__APP_NAME", "pr-warden"))

    # Private key: write resolved PEM into settings for PyGithub AppAuthentication.
    settings.set("GITHUB.PRIVATE_KEY", _read_private_key())

    # app_id MUST be a string for PyJWT (iss claim). Dynaconf may coerce to int.
    raw_app_id = os.environ.get("GITHUB__APP_ID", "").strip()
    if not raw_app_id:
        raw_app_id = str(settings.github.get("app_id", "") or "")
    settings.set("GITHUB.APP_ID", str(raw_app_id).strip())
    print(f"[warden] app_id={settings.github.app_id!r} model={settings.config.model}", flush=True)

    from pr_agent.servers.github_app import start

    start()


if __name__ == "__main__":
    main()
