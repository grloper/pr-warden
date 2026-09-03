# Security

## Reporting a vulnerability
Please **do not open a public issue** for security problems. Email the
maintainers privately (address in the repo profile) or use GitHub's
[private vulnerability reporting](https://github.com/grloper/pr-warden/security/advisories)
if enabled.

## Deployment security checklist
- The GitHub App private key must **never** leave `.secrets/` and is gitignored.
- Keep `WEBHOOK_SECRET` long and random; PR-Warden verifies the GitHub
  `X-Hub-Signature-256` on every webhook request and rejects mismatches.
- Scope the App to the **minimum repos** you trust; "All repositories" is
  convenient but exposes every repo's diff to your model backend.
- Local model (Ollama): code never leaves your machine. Cloud model: your
  diffs transit the provider — choose accordingly for private repos.
- If you expose the server beyond Tailscale/ngrok, put it behind TLS and auth.
- Rotate the App private key and webhook secret periodically (GitHub App
  settings → Private keys).

## Threat model
| Threat | Mitigation |
|---|---|
| Forged webhook | Signature verification (HMAC-SHA256) with your secret |
| App impersonation | Private key never shared; JWT signed per request |
| Secret leak in repo | `.secrets/`, `*.pem`, `.env` gitignored; manifest exchange stores only under `.secrets/` |
| Prompt injection via PR content | PR-Agent treats diff as data; reviews are advisory comments, no privileged actions |
| Code exfiltration | Local Ollama backend keeps all diffs on-machine |
