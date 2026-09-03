"""
PR-Warden configuration validation.

Catches the classic deployment mistakes before they bite at runtime:

* `app_id` must be a string (PyGithub embeds it in the JWT "iss" claim and
  PyJWT rejects non-string issuers — dynaconf can coerce numeric env values
  to int, which silently breaks App authentication).
* A private key must be resolvable.
* The model backend must be non-empty.
* Webhook secret must be present for webhook (App) mode.

Usage:
    python src/validate_config.py [--app-id 1234567] [--key .secrets/p.pem]
                                  [--secret s3cr3t] [--model ollama/x]
Exit code 0 = OK, 1 = validation failed (message printed).
"""

import argparse
import os
import sys
from pathlib import Path


def validate(app_id, private_key, webhook_secret, model, require_webhook=True):
    """Return a list of human-readable problems (empty == valid)."""
    problems = []

    # 1. app_id: must be present and a string.
    if app_id is None or str(app_id).strip() == "":
        problems.append("GitHub App ID is missing (set GITHUB_APP_ID / GITHUB__APP_ID).")
    elif not isinstance(app_id, str):
        problems.append(
            f"GitHub App ID must be a string, got {type(app_id).__name__}. "
            "PyJWT rejects int issuers; set it as a string (e.g. \"1234567\")."
        )
    elif not app_id.strip().isdigit():
        problems.append(f"GitHub App ID should be numeric, got {app_id!r}.")

    # 2. private key: present and looks like a PEM.
    key_missing = private_key is None or str(private_key).strip() == ""
    key_looks_pem = isinstance(private_key, str) and "BEGIN" in private_key
    if key_missing:
        problems.append("Private key is missing (set GITHUB__PRIVATE_KEY or place the PEM).")
    elif not key_looks_pem:
        problems.append("Private key does not look like a PEM (missing '-----BEGIN ...' header).")

    # 3. model: must be non-empty.
    if model is None or str(model).strip() == "":
        problems.append("Model is empty (set WARDEN_MODEL or CONFIG__MODEL).")

    # 4. webhook secret (only required in App/webhook mode).
    if require_webhook and (webhook_secret is None or str(webhook_secret).strip() == ""):
        problems.append("Webhook secret is missing (set WEBHOOK_SECRET).")

    return problems


def _load_env_file(path: Path) -> dict:
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PR-Warden config")
    parser.add_argument("--app-id", default=None)
    parser.add_argument("--key", default=None, help="PEM content or path to a PEM file")
    parser.add_argument("--secret", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-webhook", action="store_true", help="skip webhook-secret check (CLI mode)")
    args = parser.parse_args()

    # Precedence: CLI arg > .env > environment
    env = _load_env_file(Path(".env"))
    app_id = args.app_id or env.get("GITHUB_APP_ID") or os.environ.get("GITHUB__APP_ID")
    secret = args.secret or env.get("WEBHOOK_SECRET") or os.environ.get("GITHUB__WEBHOOK_SECRET")
    model = args.model or env.get("WARDEN_MODEL") or os.environ.get("CONFIG__MODEL")

    key = args.key or env.get("GITHUB_APP_PRIVATE_KEY") or os.environ.get("GITHUB__PRIVATE_KEY")
    if key and "BEGIN" not in key and Path(key).is_file():
        key = Path(key).read_text(encoding="utf-8")

    problems = validate(
        app_id=app_id,
        private_key=key,
        webhook_secret=secret,
        model=model,
        require_webhook=not args.no_webhook,
    )
    if problems:
        print("PR-Warden config validation FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PR-Warden config OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
