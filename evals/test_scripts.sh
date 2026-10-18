#!/usr/bin/env bash
# Deterministic tests for scripts/ (no model). Run from the repo root: bash evals/test_scripts.sh [--fast]
set -euo pipefail
python3 evals/test_scripts.py "$@"
