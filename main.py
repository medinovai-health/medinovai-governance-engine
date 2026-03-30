"""CLI entry: run API with `PYTHONPATH=src` or from Docker (see Dockerfile)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

# Allow `python main.py` from repository root without manual PYTHONPATH.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    uvicorn.run(
        "api.app:mos_app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        factory=False,
    )
