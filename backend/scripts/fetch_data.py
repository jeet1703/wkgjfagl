"""Refresh the local data snapshot from Elexon.

Usage (from backend/):  python -m scripts.fetch_data
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store.fetch_and_save()
