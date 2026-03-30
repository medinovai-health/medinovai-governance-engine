---
description: Verify environment — deps, imports, optional API smoke
---
Run `bash init.sh`. Optionally start `uvicorn api.app:mos_app` with `PYTHONPATH=src` and `curl -s localhost:8000/health`.
Report PASS/FAIL. If BROKEN, do not change `feature_list.json` passes fields.
