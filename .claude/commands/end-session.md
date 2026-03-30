---
description: Tier 1 session end — handoff and compliance reminder
---
If a feature was completed, set only `"passes": true` for that id in `feature_list.json`.
Append a new session block to `claude-progress.txt` with test method and status CLEAN or BROKEN.
Commit on a feature branch (never `main`). Summarize audit-related changes for `AUDIT_TRAIL.md` if applicable.
