"""Make the ``src`` package importable when running pytest from anywhere."""

import sys
from pathlib import Path

RAG_ROOT = Path(__file__).resolve().parent.parent
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))
