"""MindGraph tools — setup caveman import path."""
import sys
from pathlib import Path

CAVEMAN_PATH = Path(__file__).parent.parent / "caveman" / "caveman-compress"
if CAVEMAN_PATH.exists() and str(CAVEMAN_PATH) not in sys.path:
    sys.path.insert(0, str(CAVEMAN_PATH))
