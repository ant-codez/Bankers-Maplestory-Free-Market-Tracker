"""Checks the OCR-free store grid on a store captured at the game's 2x (fixtures/
store_2x.png: six items, the last sold), plus an emptied slot and a tooltip.

    python tests/slots_check.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())
import mfm  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

STORE = ROOT / "tests" / "fixtures" / "store_2x.png"
if not STORE.exists():      # captures of real stores (players' names) stay out of the repo
    print("slot checks skipped: needs a 2x store capture at tests/fixtures/store_2x.png")
    sys.exit(0)
img = Image.open(STORE).convert("RGB")
geom = {"col_x": 98 / 471, "list_top": 306 / 832}     # what read_shop learns on this store
slots = mfm.store_slots(img, geom)
assert [s for _, s in slots] == ["row"] * 5 + ["sold"], slots
assert [b for b, _ in slots] == mfm.row_boxes([324 + 80 * i for i in range(6)], img.width), slots
assert slots[0][0] == (14, 313, 412, 389)
assert mfm.slot_icon(img, slots[0][0], 98).size == (84, 84)    # _icon_crop's size for these rows

# a shop with five items leaves the last slot blank; a tooltip over slot 1 hides it
d = ImageDraw.Draw(img)
d.rectangle((98, 713 + 8, 411, 713 + 70), fill=(205, 217, 227))
d.rectangle((300, 400, 412, 460), fill=(68, 74, 124))
assert [s for _, s in mfm.store_slots(img, geom)] == ["row", "hidden", "row", "row", "row", "empty"]
print("slots OK")
