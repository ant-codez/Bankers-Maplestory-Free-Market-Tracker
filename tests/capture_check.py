"""Checks the store-only grabs between full screenshots while monitoring: a store area
(screenshot pixels) to the screen rectangle mss grabs, when a frame grabs the whole
screen instead, and the app's own windows blacked out the same in the store alone.

    python tests/capture_check.py
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

# a monitor left of the main one: its screenshot's (0, 0) is at (-2560, 0) on screen
size, origin = (2560, 1440), (-2560, 0)
assert mfm.screen_rect((753, 253, 471, 832), origin, size) == {"left": -1807, "top": 253, "width": 471, "height": 832}
assert mfm.screen_rect((0, 0, 2560, 1440), (0, 0), size) == {"left": 0, "top": 0, "width": 2560, "height": 1440}
assert mfm.screen_rect((2200, 253, 471, 832), origin, size) is None, "past the right edge"
assert mfm.screen_rect((-1, 0, 10, 10), origin, size) is None
assert mfm.screen_rect((0, 0, 0, 10), origin, size) is None

E = mfm.FULL_EVERY
assert not mfm.need_full_grab(0.1, (753, 253, 471, 832))
assert mfm.need_full_grab(E, (753, 253, 471, 832)), "the whole screen every FULL_EVERY s"
assert mfm.need_full_grab(0.1, None), "store not found yet"
assert mfm.need_full_grab(0.1, (753, 253, 471, 832), wanted=True), "megaphones / channel dialog"


class FakeMss:
    """A desktop of one monitor at `origin`; grab() records the rectangle asked for."""
    def __init__(self, origin, size):
        mon = {"left": origin[0], "top": origin[1], "width": size[0], "height": size[1]}
        self.monitors, self.asked = [mon, mon], None

    def grab(self, r):
        self.asked = r
        shot = type("Shot", (), {})()
        shot.size, shot.bgra = (r["width"], r["height"]), b"\x10\x20\x30\x00" * (r["width"] * r["height"])
        return shot


mfm._GAME_MON[:] = [1e18, 1]          # the game is on monitor 1 (not looked up)
mfm.LAST_SCREEN_SIZE[:], mfm.LAST_SCREEN_ORIGIN[:] = size, origin
sct = FakeMss(origin, size)
img = mfm.grab_store_area(sct, (753, 253, 471, 832))
assert sct.asked == {"left": -1807, "top": 253, "width": 471, "height": 832}, sct.asked
assert img.size == (471, 832) and img.getpixel((0, 0)) == (0x30, 0x20, 0x10), "BGRX to RGB"
mfm.LAST_SCREEN_ORIGIN[:] = (0, 0)    # the screenshot was taken somewhere else: grab it all again
assert mfm.grab_store_area(sct, (753, 253, 471, 832)) is None
mfm.LAST_SCREEN_ORIGIN[:] = origin

# the app's own window over the store: blacked out at the same pixels in both
mfm.GRAB_MODE[0] = "screen"
m = mfm.Monitor(mfm.load_config())
m.own_windows = lambda: [(-1807 + 100, 253 + 200, 300, 5000)]
full = Image.new("RGB", size, (200, 200, 200))
store = Image.new("RGB", (471, 832), (200, 200, 200))
m._hide_own_windows(full)
m._hide_own_windows(store, (-1807, 253))
assert list(mfm.crop(full, (753, 253, 471, 832)).getdata()) == list(store.getdata())
assert store.getpixel((100, 200)) == (0, 0, 0) and store.getpixel((99, 200)) == (200, 200, 200)
print("capture OK")
