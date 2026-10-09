#!/usr/bin/env bash
# Single source of truth for 'is this change OK'. Exit code is the truth.
# Only checks that pass on main today are included (formatters are not enabled where they would fail).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

python -m ruff check --select E4,E7,E9,F --ignore F401,F541 src tests
python -m py_compile src/warden.py src/manifest.py src/run_server.py src/validate_config.py
python -m unittest discover -s tests -v
echo "verify: ALL CHECKS PASSED"
