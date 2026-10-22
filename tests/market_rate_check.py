"""Checks mfm.market_rate's order: sold median (MIN_SALES+ sales), then listed
median (min_sightings+ listings), then an imported reference price, then the
median of everything seen; outliers never count.

    python tests/market_rate_check.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())
import mfm  # noqa: E402

con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE listings (item TEXT, price INTEGER, qty INTEGER DEFAULT 1, ts TEXT, "
            "last_seen TEXT, sold INTEGER DEFAULT 0)")
con.execute("CREATE TABLE reference (item TEXT PRIMARY KEY, price INTEGER, source TEXT, updated TEXT)")
con.executemany("INSERT INTO reference VALUES (?, 1000, 'site', '')", [("Ore",), ("Gem",)])
cfg = dict(mfm.DEFAULT_CONFIG)
now = mfm.utc_now()


def add(item, price, sold=0, n=1):
    con.executemany("INSERT INTO listings (item, price, ts, sold) VALUES (?, ?, ?, ?)",
                    [(item, price, now, sold)] * n)


def rate(item):
    return mfm.market_rate(con, item, cfg)


assert rate("Ore") == (1000, "site"), "no scans: reference"
add("Ore", 700, n=4)
assert rate("Ore") == (1000, "site"), "too few sightings: reference"
add("Ore", 700)
assert rate("Ore") == (700, "median of 5 listed"), rate("Ore")
add("Ore", 600, sold=1, n=2)
assert rate("Ore") == (700, "median of 5 listed"), "2 sales aren't enough: listed median"
add("Ore", 650, sold=1)
assert rate("Ore") == (600, "median of 3 sold"), rate("Ore")
add("Ore", 9000, sold=1)   # godly / mistyped sale: over 3x the usual price, left out
assert rate("Ore") == (600, "median of 3 sold, 1 outlier ignored"), rate("Ore")

# enough sightings, but too few sales and too few listings: reference, else everything seen
add("Gem", 400, n=3)
add("Gem", 500, sold=1, n=2)
assert rate("Gem") == (1000, "site"), rate("Gem")
con.execute("DELETE FROM reference WHERE item = 'Gem'")
assert rate("Gem") == (400, "median of 5 seen"), rate("Gem")
assert rate("Nope") == (None, "not enough data (0 of 5 sightings)")
print("market_rate OK")
