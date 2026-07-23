#!/usr/bin/env python3
"""Source-tree launcher for the nmr2boltz package.

For a normal installation use ``nmr2boltz convert ...``. This wrapper also works
from an unpacked source bundle after installing the dependencies.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nmr2boltz.cli import main  # noqa: E402

raise SystemExit(main())
