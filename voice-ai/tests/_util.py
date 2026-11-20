"""Shared paths for the tests."""
from __future__ import annotations

import sys
from pathlib import Path

VA = Path(__file__).resolve().parent.parent  # voice-ai/
EDITIONS = ("global", "india")
LABS = sorted(p.name for p in (VA / "labs").iterdir() if p.is_dir())
SOLUTIONS = sorted(p.stem for p in (VA / "solutions").glob("m[0-9][0-9]_*.py"))
PY = sys.executable

if str(VA) not in sys.path:
    sys.path.insert(0, str(VA))
