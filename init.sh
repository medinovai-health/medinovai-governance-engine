#!/usr/bin/env bash
# init.sh — MedinovAI Harness 2.1
# Repo: medinovai-governance-engine
# Tier: 1 (FDA / 21 CFR Part 11 — clinical data governance)
# Validates Python 3.11+, installs deps, smoke-imports FastAPI app and Temporal modules.

set -euo pipefail

echo "=== MedinovAI init.sh (governance-engine) ==="
echo "Repo: medinovai-governance-engine"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Python: $PYVER"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

VENV_PY="${ROOT}/.venv/bin/python"
# Recover from mixed-arch / corrupted wheels (e.g. arm64 site-packages with x86_64 interpreter).
if [[ -x "$VENV_PY" ]] && ! "$VENV_PY" -c "import pydantic_core" 2>/dev/null; then
  echo "WARN: rebuilding .venv (import check failed — often arch mismatch)"
  python3 -m venv --clear .venv
fi
if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: venv python missing at $VENV_PY"
  exit 1
fi

"$VENV_PY" -m pip install --upgrade pip >/dev/null
"$VENV_PY" -m pip install -r requirements.txt

export PYTHONPATH="${ROOT}/src"

"$VENV_PY" -c "from api.app import mos_app; assert mos_app.title"
"$VENV_PY" -c "from governance.query_workflow import QueryApprovalWorkflow; assert QueryApprovalWorkflow"
"$VENV_PY" -c "from temporalio.client import Client"

echo "Smoke import: PASS"
echo "Start API: PYTHONPATH=src uvicorn api.app:mos_app --host 0.0.0.0 --port 8000"
echo "Start Temporal worker: PYTHONPATH=src python src/temporal_worker.py (from repo root)"
echo "Docker stack: docker compose up --build"
echo "=== init.sh complete ==="
