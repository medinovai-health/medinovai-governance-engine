# CLAUDE.md — medinovai-governance-engine

> This file is read by every Claude agent at the start of each session.  
> Keep it accurate. It is the agent's primary source of truth about this repo.

## Purpose

**medinovai-governance-engine** is a **Tier 1** (FDA-relevant) **Phase E Sprint 4** service that enforces **data use agreements (DUAs)**, **query approval workflows** (Temporal-backed), **governance policies** (minimum cell size, linkage rules, re-identification risk scoring), and **Evidence Store** integration for **electronic signatures**, **audit trails**, and **artifact lineage**. Researchers submit queries; data stewards review; sensitive queries require multiple e-signatures per policy.

## Compliance Tier

| Field | Value |
|-------|-------|
| **Harness Tier** | **1** (Tier 1 — FDA / clinical governance) |
| **Platform tier** | 1 (security / compliance plane) |
| **Regulatory** | HIPAA, GDPR, **21 CFR Part 11**, ISO 13485, IEC 62304 (downstream traceability) |
| **PHI in this service** | **None by design** in API payloads — only IDs, purpose codes, and opaque spec handles. Never log raw query text or PHI. |

### Tier 1 annotations (mandatory)

- **§21 CFR Part 11**: All approvals must map to **electronic signature** records (meaning, actor, timestamp) via Evidence Store; see `AUDIT_TRAIL.md`.
- **Audit**: Mutations (submit, approve, deny, DUA store) emit **structured audit events** (`category=AUDIT`, `phi_safe=true`).
- **Fail-safe**: If Temporal is unavailable, API remains up; workflows degrade to `local_only` while **audit stubs** still record intent (replace with durable store in production).
- **Traceability**: Each deliverable feature lists `requirements` in `feature_list.json` — link implements to specs (`specs/active/medinovai-2in-governance-engine/specification.yaml` in Developer repo).

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn  
- **Workflows:** Temporal (Python SDK) — task queue `governance-query-approval`  
- **HTTP client:** httpx (Evidence Store)  
- **Logging:** structlog (JSON)

## How to Start the Dev Server

```bash
bash init.sh
source .venv/bin/activate
export PYTHONPATH=src
uvicorn api.app:mos_app --host 0.0.0.0 --port 8000
```

- **Health:** `GET http://localhost:8000/health`  
- **Ready:** `GET http://localhost:8000/ready`

## Temporal Worker

```bash
export PYTHONPATH=src
python src/temporal_worker.py
```

## Docker + Temporal Stack

```bash
docker compose up --build
```

- **API:** `http://localhost:8000`  
- **Temporal gRPC:** `localhost:7233`  
- **Temporal UI:** `http://localhost:8088`  
- **Postgres (Temporal):** host `localhost:5433`

Environment:

- `TEMPORAL_ADDRESS` (default `localhost:7233`)  
- `EVIDENCE_STORE_URL` (optional; empty = stub signatures/audit)

## How to Run Tests

Scaffold phase — add `pytest` in a follow-up session. Target:

```bash
pytest tests/unit tests/integration
```

Minimum coverage goal: **80%** on governance and API layers.

## Coding Conventions (MedinovAI Standard)

- Constants: `E_*`; variables: `mos_*`  
- Methods: max **40 lines**  
- Docstrings: **Google style**; type hints on all public functions  
- Logging: **structlog**, JSON, **never** log PHI or raw query payloads  
- Secrets: platform secrets manager only — **no** secrets in repo

## API Layout

| Area | Prefix |
|------|--------|
| Health | `/health`, `/ready` |
| DUA | `/api/v1/dua/*` |
| Query | `/api/v1/query/*` |
| Governance | `/api/v1/governance/*` |

## Git Branch Strategy

- `main`: release-ready only — **no direct agent commits**  
- Features: `feature/F###-short-description`  
- PR + review required for merge

## Known Issues / Current State

- `init.sh` runs `python3 -m venv --clear .venv` when `pydantic_core` fails to import (common **Rosetta / mixed-arch** `.venv`); use one consistent `python3` for the team.
- In-memory DUA and query stores — **replace with persistent DB** and SpiceDB checks.  
- Evidence Store client **stubs** when `EVIDENCE_STORE_URL` unset.  
- OpenAPI: `GET /docs` (FastAPI) — publish to `data-contracts` in Developer repo when API stabilizes.

## 9. CLAUDE.md Standard — Harness 2.1 (Tier 1 profile)

This section mirrors **Harness 2.1 §9** with **Tier 1** fields filled for this repository.

### Purpose (template §9)

Enforce DUAs, governed query approval, privacy policies, and regulatory auditability for the Integration Platform research path.

### Compliance Tier (template §9)

**Tier 1** — Applicable: **HIPAA**, **GDPR**, **21 CFR Part 11**, **ISO 13485**, **IEC 62304** (traceability to `feature_list.json`).

### Tier 1 Compliance Requirements (template §9 — do not skip)

- Encrypt PHI **at rest and in transit** in all deployments that attach clinical stores (this service stays ID-only at the boundary).  
- Log access and governance decisions to **Evidence Store / WORM** audit path.  
- Electronic signatures: **identity, timestamp, meaning** — see `integration/evidence_store.py` and `AUDIT_TRAIL.md`.  
- **IEC 62304**: requirement IDs in `feature_list.json` → tests → implementation.

### Context injection order (every session)

1. `pwd`  
2. Read `claude-progress.txt`  
3. Read `feature_list.json` (pick **one** `passes: false`)  
4. `git log --oneline -20`  
5. Run `bash init.sh`  
6. Implement + test  
7. Set **only** `passes: true` for completed feature; commit; append progress log  

## Last Updated

2026-03-30 — Initial scaffold (Harness 2.1 Tier 1).
