"""
Palette/style constants shared with NovInvenio's lib/figures.py, so this dashboard's HTML/JS
and any later PDF export read as the same visual system as view/Exophiala/*.html.

Tries to import the canonical constants from NovInvenio (this project's db/ symlink already
points at /rhome/jstajich/projects/NovInvenio, so that's the known-good location today); falls
back to a hardcoded copy if NovInvenio's lib/ isn't importable, so this module still works if
the dashboard is later extracted into its own repo without that neighbor project on disk.
"""
import sys
from pathlib import Path

_NOVINVENIO_LIB = Path("/rhome/jstajich/projects/NovInvenio/lib")

try:
    if str(_NOVINVENIO_LIB) not in sys.path and _NOVINVENIO_LIB.is_dir():
        sys.path.insert(0, str(_NOVINVENIO_LIB))
    from figures import BLUE, GREEN, ORANGE, PURPLE, GRID, AXIS, INK, MUTED, ABSENT, CATEGORICAL
except ImportError:
    # Fallback copy (kept identical to NovInvenio/lib/figures.py) for portability.
    BLUE = "#2a78d6"
    GREEN = "#008300"
    ORANGE = "#e69f00"
    PURPLE = "#cc79a7"
    GRID = "#e1e0d9"
    AXIS = "#c3c2b7"
    INK = "#0b0b0b"
    MUTED = "#898781"
    ABSENT = "#ecebe4"
    CATEGORICAL = [BLUE, ORANGE, PURPLE, GREEN]

# Extra series colors needed for up to ~7 GENUS/group categories in this dataset (still
# CVD-safe: Okabe-Ito derived), appended after the 4 already validated in NovInvenio.
CATEGORICAL_EXTENDED = CATEGORICAL + ["#56b4e9", "#009e73", "#d55e00"]

PALETTE_JSON = {
    "blue": BLUE,
    "green": GREEN,
    "orange": ORANGE,
    "purple": PURPLE,
    "grid": GRID,
    "axis": AXIS,
    "ink": INK,
    "muted": MUTED,
    "absent": ABSENT,
    "categorical": CATEGORICAL_EXTENDED,
}
