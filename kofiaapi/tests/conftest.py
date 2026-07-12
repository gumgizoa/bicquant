"""Pytest can place the project directory before src/, resolving ``kofiaapi`` as a
namespace package. Force the real src package before test modules import it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if "kofiaapi" in sys.modules and getattr(sys.modules["kofiaapi"], "__file__", None) is None:
    del sys.modules["kofiaapi"]
