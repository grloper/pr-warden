# PR Warden

A self-hosting wrapper around the upstream PR-Agent review engine, with GitHub App configuration helpers, model-endpoint probes, review orchestration and repository-question helpers. PR-Agent supplies the underlying review engine; this repository supplies configuration and integration code around it.

## Executed evidence

The Windows audit passed 26 helper tests using local files, fake provider clients and a loopback endpoint. Configuration parsing, manifest behavior, helper logic and bounded network probes were exercised. An actual model-generated PR review or posted GitHub review was not performed.

Use Python 3.11+ in a dedicated environment for local checks:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python src/warden.py --help
python src/manifest.py --help
```

`src/warden.py` orchestrates review; `run_server.py` handles application serving; `manifest.py` and `validate_config.py` help configure the GitHub App; `askrepo.py` and `insights.py` provide additional helpers. Installing the optional `engine` extra adds PR-Agent; a real model endpoint and authorized GitHub integration are separate requirements.

## Boundaries

Local Ollama hosting still consumes hardware and electricity; cloud models can incur provider costs and transmit code. No zero-cost, production-grade, universal bug detection or never-leaves-your-machine guarantee is established. Actual model quality, external webhook behavior, PR posting and production deployment remain unverified. This is a developer integration prototype, not an independently validated review service.
