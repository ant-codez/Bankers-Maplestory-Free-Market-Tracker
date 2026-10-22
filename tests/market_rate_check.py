"""Checks mfm.market_rate's order: an imported reference price is used until the
item has enough sightings and 2+ sales of its own, then the sold median wins.

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
con.execute("INSERT INTO reference VALUES ('Ore', 1000, 'site', '')")
cfg = dict(mfm.DEFAULT_CONFIG)
now = mfm.utc_now()


def add(price, sold=0, n=1):
    con.executemany("INSERT INTO listings (item, price, ts, sold) VALUES ('Ore', ?, ?, ?)",
                    [(price, now, sold)] * n)


assert mfm.market_rate(con, "Ore", cfg) == (1000, "site"), "no scans: reference"
add(700, n=4)
assert mfm.market_rate(con, "Ore", cfg) == (1000, "site"), "too few sightings: reference"
add(700, sold=1)
assert mfm.market_rate(con, "Ore", cfg) == (1000, "site"), "only 1 sale: reference"
add(600, sold=1)
assert mfm.market_rate(con, "Ore", cfg) == (1000, "site"), "2 sales don't beat a reference"
add(650, sold=1)
price, how = mfm.market_rate(con, "Ore", cfg)
assert price == 650 and how.startswith("median of 3 sold"), (price, how)
add(9000, sold=1)   # godly / mistyped sale: over 3x the usual price, left out
price, how = mfm.market_rate(con, "Ore", cfg)
assert price == 650 and "1 outlier ignored" in how, (price, how)
assert mfm.market_rate(con, "Gem", cfg) == (None, "not enough data (0 of 5 sightings)")
print("market_rate OK")
