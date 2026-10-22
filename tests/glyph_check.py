"""Checks the glyph price reader on a store captured at the game's 2x (fixtures/
store_2x.png, prices checked by eye), and that learn_glyphs refuses a misread.

    python tests/glyph_check.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())
import mfm  # noqa: E402
from PIL import Image  # noqa: E402

mfm.GLYPHS_PATH = Path(tempfile.mkdtemp()) / "glyphs.json"     # learn into a throwaway file
STORE = ROOT / "tests" / "fixtures" / "store_2x.png"
if not STORE.exists():      # captures of real stores (players' names) stay out of the repo
    print("glyph checks skipped: needs a 2x store capture at tests/fixtures/store_2x.png")
    sys.exit(0)
img = Image.open(STORE).convert("RGB")
boxes = mfm.row_boxes([324 + 80 * i for i in range(6)], img.width)   # this layout's six rows
col_x = 98
want = [25555, 77777, 88888, 44444, 29999, 24444]               # 88,888: Tesseract at 3 read 68,888
got = [mfm.glyph_price(img, b, col_x) for b in boxes]
assert got == want, got

# a misread can't teach a wrong digit: 77,777 told as 77,177 gives "1" a 7's shape
assert not mfm.learn_glyphs(img, boxes[1], col_x, 77177)
assert mfm.learn_glyphs(img, boxes[1], col_x, 77777)
assert mfm.glyph_price(img, boxes[1], col_x) == 77777
print("glyphs OK")

# names: the shipped name glyphs spell each row's item (I and l alike, spaces
# ignored), matched against the official names; the sold last row too
names = ["Emerald Earrings", "Green Icarus Cape", "Titan", "Blue Sauna Robe", "Dark Burgler",
         "Emerald Earring", "Titans", "Green Icarus"]                     # near misses must lose
mfm._Dictionary.cache = mfm._Dictionary(names)
mfm.NAME_GLYPHS_PATH = Path(tempfile.mkdtemp()) / "name_glyphs.json"
got = [mfm.glyph_name(img, b, col_x) for b in boxes]
assert got == ["Emerald Earrings", "Green Icarus Cape", "Titan", "Titan", "Blue Sauna Robe",
               "Dark Burgler"], got
# a wrong name can't be taught: "Titan" doesn't spell "Emerald Earrings"
assert not mfm.learn_name(img, boxes[2], col_x, "Emerald Earrings")
print("names OK")

# the row cache: the same row pixels lower down (a scroll) read from the cache, with
# the price box moved along with the row
mfm._ROW_CACHE.clear()
first = mfm._glyph_row(img, boxes[0], col_x)
moved = img.copy()
moved.paste(img.crop(boxes[0]), (boxes[2][0], boxes[2][1]))
read_at = []
real = mfm.glyph_read
mfm.glyph_read = lambda *a: read_at.append(a[1]) or real(*a)
again = mfm._glyph_row(moved, boxes[2], col_x)
mfm.glyph_read = real
assert read_at == [], "served from the cache"
dy = boxes[2][1] - boxes[0][1]
assert again == (first[0], (first[1][0], first[1][1] + dy, first[1][2], first[1][3] + dy), first[2]), again
print("row cache OK")

# a double quote is drawn as two ' glyphs, and "rt" in "Shirt" touch (one unknown
# glyph): fixtures/store_quotes_2x.png's last row is Black "Hit Me" Shirt
QUOTES = ROOT / "tests" / "fixtures" / "store_quotes_2x.png"
if not QUOTES.exists():
    print("quotes skipped: needs tests/fixtures/store_quotes_2x.png")
    sys.exit(0)
quotes = Image.open(QUOTES).convert("RGB")
mfm._Dictionary.cache = mfm._Dictionary(['Black "Hit Me" Shirt', "Black Hat", "Black Shirt"])
assert mfm.glyph_name(quotes, boxes[5], col_x) == 'Black "Hit Me" Shirt'
print("quotes OK")
