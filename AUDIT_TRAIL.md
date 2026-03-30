# Audit Trail — medinovai-governance-engine

**System:** medinovai-governance-engine  
**Version:** 0.1.0  
**Classification:** Internal QMS / Compliance  
**Regulatory basis:** 21 CFR Part 11 (Electronic Records; Electronic Signatures), HIPAA Security Rule (audit controls), ISO 13485 (quality records)

---

## 1. System Description (§11.10(a))

This service records **governance decisions** for research data access: DUA compliance checks, query submission, steward approval/denial, policy evaluations, and integration handoff to the **Evidence Store** for **non-repudiation** and **record integrity**.

**Boundaries:** API payloads are **identifier- and metadata-only** at the scaffold; production deployments must **not** attach free-text PHI to audit events.

---

## 2. Electronic Records (§11.10(b)–(e))

| Control | Implementation (target) |
|---------|-------------------------|
| Record generation | Structured JSON events via `EvidenceStoreClient.append_audit_event` |
| Accurate copies | Evidence Store WORM / object lock; correlation IDs |
| Record protection | TLS 1.3 in transit; access via MSS + SpiceDB |
| Retention | Platform retention policy; DUA and query records per sponsor agreement |

---

## 3. Electronic Signatures (§11.50, §11.70, §11.100, §11.200)

| Element | MedinovAI mapping |
|---------|-------------------|
| **Printed name** | `actor_id` (resolved to display name in IdP — not stored in engine logs) |
| **Date and time** | ISO-8601 UTC from Evidence Store or service timestamp |
| **Meaning** | e.g. `query_approval`, `dua_attestation` — passed to `request_electronic_signature` |
| **Signature uniqueness** | `signature_id` from Evidence Store |
| **Non-repudiation** | Evidence Store cryptographic binding (production); stub UUID in dev |

**Multi-signature:** Sensitive queries use `signatures_required` > 1; Temporal workflow `QueryApprovalWorkflow` gates `finalize_approve` until quorum.

---

## 4. Audit Trail Events (initial catalog)

| event_type | When | phi_safe |
|------------|------|----------|
| `query_submitted` | POST `/api/v1/query/submit` | true |
| `query_approved` | POST `/api/v1/query/{id}/approve` | true |
| `query_denied` | POST `/api/v1/query/{id}/deny` | true |
| `dua_stored` | DUA persisted | true |
| `policy_registered` | POST `/api/v1/governance/policies` | true |
| `evidence_signature_stub` | Dev mode without Evidence URL | true |
| `evidence_audit_stub` | Dev mode audit append | true |

---

## 5. Operator Accountability

| Role | Responsibility |
|------|----------------|
| Data steward | Approve/deny against DUA and policy |
| Security | RBAC, tenant isolation, Evidence Store ACLs |
| QA | Verify `feature_list.json` compliance features before release |

---

## 6. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-03-30 | Platform | Initial 21 CFR Part 11 format scaffold |
