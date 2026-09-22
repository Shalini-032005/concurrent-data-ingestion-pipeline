import sys
from pathlib import Path

# Ensure `app` and `main` are importable when running `pytest` from the
# backend/ directory or from the repo root.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
