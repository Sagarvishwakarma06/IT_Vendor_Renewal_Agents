"""pytest conftest.py — ensures src is importable from the project root."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
