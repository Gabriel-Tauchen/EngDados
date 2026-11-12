"""Main entrypoint delegating to pipeline.py for convenience."""
import sys
from pathlib import Path

# Add src to sys.path so modules can be imported directly
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pipeline import main

if __name__ == "__main__":
    stage_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(stage_arg)
