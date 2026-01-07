from pathlib import Path

here = Path(__file__).parent
with open(here.parent / "VERSION.txt", "r") as vf:
    __version__ = vf.read().strip()
