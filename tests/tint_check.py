"""Checks the deal tint's geometry: mfm.row_boxes (store rows from their name lines,
measured on a real store at 2x: rows 80 px apart, the faded last one read 13 px
off), mfm.glyph_read's box around just the price ("25,555 mesos", not "1 for"),
and Monitor._send_tint turning DEAL / fair / HIGH prices into screen rectangles.

    python tests/tint_check.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())
import mfm  # noqa: E402

boxes = mfm.row_boxes([324, 404, 484, 564, 644, 711], 471)
assert boxes[0] == (14, 313, 412, 389), boxes[0]
assert boxes[-1] == (14, 713, 412, 789), "faded row snapped to the row spacing"
assert mfm.row_boxes([324], 471, 56) == [(14, 313, 412, 389)], "a lone row sized from its text"
assert mfm.row_boxes([324], 471) == [None] and mfm.row_boxes([], 471) == []

from PIL import Image  # noqa: E402
img = Image.open(ROOT / "tests" / "fixtures" / "store_2x.png").convert("RGB")
row = mfm.row_boxes([324 + 80 * i for i in range(6)], img.width)[0]    # "1 for 25,555 mesos"
spans = []
mfm.price_glyphs(img, row, 98, spans)
price, (x0, y0, x1, y1) = mfm.glyph_read(img, row, 98)
assert price == 25555
assert spans[3][2] <= x0 < spans[4][0], "starts after \"for\", at the 2"     # glyphs: 1 f o r 2 ...
assert x1 >= spans[-1][2] and x1 - x0 > 0.9 * (spans[-1][2] - spans[4][0]), "through \"mesos\""
assert y0 > row[1] + 0.4 * (row[3] - row[1]) and y1 <= row[3], "the price line only"

events = []
m = mfm.Monitor(dict(mfm.DEFAULT_CONFIG), lambda k, p: events.append((k, p)))
m._shop_at = ([3313, 253, 471, 832], (-2560, 0))      # store area in the capture, its origin
ls = [mfm.Listing("A", 1, 1, "", box=b, price_box=(150, b[1] + 43, 312, b[1] + 71)) for b in boxes]
m.last_listings, m.last_keys = ls, [(k,) for k in "ABCDEF"]
m.seen = {k: mfm.SeenListing("x", 1, 1, 1, 1, v, 0, "") for k, v in
          zip(m.last_keys, ("DEAL", "fair", "HIGH", "SOLD", "OUTLIER", "?"))}
m._send_tint()
assert events == [("tint", [(903, 609, 162, 28, "DEAL"), (903, 689, 162, 28, "fair"),
                            (903, 769, 162, 28, "HIGH"), (903, 929, 162, 28, "OUTLIER"),
                            (903, 1009, 162, 28, "?")])], events
m._send_tint()
assert len(events) == 1, "unchanged rows aren't sent again"
ls[0].price_box = None
m._send_tint()
assert [r[4] for r in events[-1][1]] == ["fair", "HIGH", "OUTLIER", "?"], "no price box: no tint"
m.cfg["tint_on"] = False
m._send_tint()
assert events[-1] == ("tint", []), "turned off: cleared"

# hovering: rows under the cursor / tooltip aren't read, but keep their colour
# until the list scrolls (scroll_thumb) or moves, or the visit ends
verdicts = lambda: [r[4] for r in m._tint]     # noqa: E731
m.cfg["tint_on"] = True
ls[0].price_box = (150, boxes[0][1] + 43, 312, boxes[0][1] + 71)
m._list_at = ((3313, 253, 471, 832), 711)
m._send_tint()
assert verdicts() == ["DEAL", "fair", "HIGH", "OUTLIER", "?"]
n = len(events)
m.last_listings, m.last_keys = ls[3:], m.last_keys[3:]      # rows A-C hidden
m._send_tint()
assert verdicts() == ["DEAL", "fair", "HIGH", "OUTLIER", "?"] and len(events) == n, "hidden rows keep their tint"
m.seen[("G",)] = mfm.SeenListing("x", 1, 1, 1, 1, "HIGH", 0, "")
m.last_listings, m.last_keys = [ls[0], ls[1]], [("D",), ("G",)]   # A now sold, B now HIGH
m._send_tint()
assert verdicts() == ["HIGH", "HIGH", "OUTLIER", "?"], "a row read again takes its new verdict, or none"
m._list_at = ((3313, 253, 471, 832), 463)                   # scrolled
m.last_listings, m.last_keys = ls[3:], [(k,) for k in "DEF"]
m._send_tint()
assert verdicts() == ["OUTLIER", "?"], "a scroll forgets the remembered rows: only E, F, read again"
m.last_listings, m.last_keys = ls, [(k,) for k in "ABCDEF"]
m._send_tint()
assert verdicts() == ["DEAL", "fair", "HIGH", "OUTLIER", "?"]
m.end_session()
m._send_tint()
assert events[-1] == ("tint", []), "a new visit forgets them too"

# the scroll position: the thumb's top, not moved by a cursor / tooltip over the rows
assert mfm.scroll_thumb(img) == 711
covered = img.copy()
covered.paste((60, 70, 140), (200, 500, 400, 832))           # a tooltip over the rows
covered.paste((255, 255, 255), (300, 400, 330, 440))         # the cursor
assert mfm.scroll_thumb(covered) == 711
covered.paste((60, 70, 140), (300, 600, 471, 832))           # ... and over the thumb: unknown
assert mfm.scroll_thumb(covered) is None
moved = img.copy()
moved.paste(img.crop((415, 711, 471, 761)), (415, 463))
moved.paste(img.crop((415, 400, 471, 450)), (415, 711))      # bare track where it was
assert mfm.scroll_thumb(moved) == 463
print("tint OK")
