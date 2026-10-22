"""Checks the deal tint's geometry: mfm.row_boxes (store rows from their name lines,
measured on a real store at 2x: rows 80 px apart, the faded last one read 13 px
off), and Monitor._send_tint turning DEAL / HIGH rows into screen rectangles.

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

events = []
m = mfm.Monitor(dict(mfm.DEFAULT_CONFIG), lambda k, p: events.append((k, p)))
m._shop_at = ([3313, 253, 471, 832], (-2560, 0))      # store area in the capture, its origin
deal, fair, high = (mfm.Listing("A", 1, 1, "", box=b) for b in boxes[:3])
m.last_listings, m.last_keys = [deal, fair, high], [("A",), ("B",), ("C",)]
m.seen = {k: mfm.SeenListing("x", 1, 1, 1, 1, v, 0, "") for k, v in
          zip(m.last_keys, ("DEAL", "fair", "HIGH"))}
m._send_tint()
assert events == [("tint", [(767, 566, 398, 76, "DEAL"), (767, 726, 398, 76, "HIGH")])], events
m._send_tint()
assert len(events) == 1, "unchanged rows aren't sent again"
m.cfg["tint_on"] = False
m._send_tint()
assert events[-1] == ("tint", []), "turned off: cleared"
print("tint OK")
