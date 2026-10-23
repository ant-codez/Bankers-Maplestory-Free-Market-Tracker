"""Checks the MesoWatch import: parse_mesowatch reading JSON (list, {"items"},
name-keyed) and CSV with loose field names and "35K"-style values,
import_mesowatch matching names to the item dictionary, market_rate/verdict/fmt
on fresh and stale rows, set_range keeping a typical, and db() moving an old
`ranges` table into `mesowatch`. Runs on a throwaway data dir.

    python tests/mesowatch_check.py
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(TMP)            # Windows: mfm.data_dir() lives here, not in your real data
os.environ["XDG_DATA_HOME"] = str(TMP)      # elsewhere
import mfm  # noqa: E402

assert TMP in mfm.DB_PATH.parents, mfm.DB_PATH
cfg = dict(mfm.DEFAULT_CONFIG)


def write(name, text):
    p = TMP / name
    p.write_text(text, encoding="utf-8")
    return p


def parse_json(data):
    return mfm.parse_mesowatch(write("mw.json", json.dumps(data)))


def by_item(entries):
    return {e["item"]: e for e in entries}


# migration: yesterday's `ranges` table moves into `mesowatch` on the first db()
mfm.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
old = sqlite3.connect(mfm.DB_PATH)
old.execute("CREATE TABLE ranges (item TEXT PRIMARY KEY, low INTEGER, high INTEGER, source TEXT, updated TEXT)")
old.execute("INSERT INTO ranges VALUES ('Steel Pride', 1100000, 1300000, 'MesoWatch', ?)", (mfm.utc_now(),))
old.commit()
old.close()
con = mfm.db()
assert not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ranges'").fetchone()
info = mfm.mesowatch_info(con, "Steel Pride")
assert (info["low"], info["high"]) == (1100000, 1300000), info
assert set(info) >= {"item", "typical", "low", "high", "volume", "total_volume", "total_sales",
                     "source", "updated"}, info
got, how = mfm.market_rate(con, "Steel Pride", cfg)
assert isinstance(got, mfm.MarketRange) and int(got) == 1200000 and how.startswith("MesoWatch"), (got, how)
assert mfm.mesowatch_info(con, "Nothing Here") is None
print("migration OK")

# JSON list: every field, aliases, case/space/dash/camelCase names, "35K" values
entries, problems = parse_json([
    {"item": "Baby Angel Wings", "typical": "37.5K", "range": "35K - 40K",
     "volume": 42, "total_volume": 1890, "total_sales": 678},
    {"Name": "Angel Halo", "Typical Price": "52,000", "typical-low": "48k", "Typical_High": "55K",
     "Volume": "18", "totalVolume": 640, "TotalSales": "231", "watchUnder": "45K"},
    {"item": "Blue Sauna Robe", "price": 180000, "min": 200000, "max": 160000, "sales": 97},   # swapped
    {"typical": 5000},                                                                         # no item
    {"item": "Steel Pride"},                                                                   # no numbers
    {"item": "White Beanie", "range": "35k–40k", "maxEach": "30K"},
    {"item": "Red Bandana", "typicalRange": "1.2m to 1.5m", "alert_under": 1_000_000},
    {"item": "Bad Range", "range": "cheap"},                                                   # unreadable
])
e = by_item(entries)
assert set(e["Baby Angel Wings"]) == {"item", "typical", "low", "high", "volume", "total_volume",
                                      "total_sales", "change_24h", "watch_under"}, e["Baby Angel Wings"]
assert e["Baby Angel Wings"] == {"item": "Baby Angel Wings", "typical": 37500, "low": 35000, "high": 40000,
                                 "volume": 42, "total_volume": 1890, "total_sales": 678,
                                 "change_24h": None, "watch_under": None}, e["Baby Angel Wings"]
assert e["Angel Halo"] == {"item": "Angel Halo", "typical": 52000, "low": 48000, "high": 55000, "volume": 18,
                           "total_volume": 640, "total_sales": 231, "change_24h": None, "watch_under": 45000}, e["Angel Halo"]
bsr = e["Blue Sauna Robe"]
assert (bsr["typical"], bsr["low"], bsr["high"], bsr["total_sales"]) == (180000, 160000, 200000, 97), bsr
wb = e["White Beanie"]
assert (wb["typical"], wb["low"], wb["high"], wb["watch_under"]) == (None, 35000, 40000, 30000), wb
rb = e["Red Bandana"]
assert (rb["low"], rb["high"], rb["watch_under"]) == (1200000, 1500000, 1000000), rb
assert "Steel Pride" not in e and None not in e and "" not in e, list(e)
rows = sorted(n for n, _ in problems)
assert rows[:2] == [4, 5] and 8 in rows, problems
assert all(isinstance(r, str) and r for _, r in problems), problems
print("parse json OK")

# {"items": [...]} and a name-keyed object
entries, problems = parse_json({"items": [{"item": "Angel Halo", "typical": "52K"}]})
assert [(x["item"], x["typical"]) for x in entries] == [("Angel Halo", 52000)] and not problems
entries, problems = parse_json({"Angel Halo": {"typical": "52K", "range": "48K - 55K"},
                                "White Beanie": {"Typical Price": 6500}})
e = by_item(entries)
assert (e["Angel Halo"]["typical"], e["Angel Halo"]["low"], e["Angel Halo"]["high"]) == (52000, 48000, 55000)
assert e["White Beanie"]["typical"] == 6500 and not problems, (entries, problems)
print("parse json shapes OK")

# CSV with the same loose headers
csv_entries, csv_problems = mfm.parse_mesowatch(write("mw.csv", (
    "Name,Typical Price,typical-low,Typical_High,range,totalVolume,TotalSales,watchUnder\n"
    'Angel Halo,"52,000",48k,55K,,640,231,45K\n'
    "Blue Sauna Robe,180K,200000,160000,,,97,\n"
    ",5000,,,,,,\n"
    "Steel Pride,,,,,,,\n"
    "Baby Angel Wings,37.5K,,,35K - 40K,1890,678,\n")))
e = by_item(csv_entries)
assert (e["Angel Halo"]["typical"], e["Angel Halo"]["low"], e["Angel Halo"]["high"],
        e["Angel Halo"]["total_volume"], e["Angel Halo"]["watch_under"]) == (52000, 48000, 55000, 640, 45000)
assert (e["Blue Sauna Robe"]["low"], e["Blue Sauna Robe"]["high"]) == (160000, 200000)
assert (e["Baby Angel Wings"]["low"], e["Baby Angel Wings"]["high"]) == (35000, 40000)
assert e["Blue Sauna Robe"]["volume"] is None and "Steel Pride" not in e, e
assert sorted(n for n, _ in csv_problems) == [3, 4], csv_problems     # data rows, header not counted
print("parse csv OK")

# the shipped examples parse cleanly and agree with each other
ej, pj = mfm.parse_mesowatch(ROOT / "docs" / "mesowatch-import-example.json")
ec, pc = mfm.parse_mesowatch(ROOT / "docs" / "mesowatch-import-example.csv")
assert not pj and not pc, (pj, pc)
assert by_item(ej) == by_item(ec) and len(ej) == 5, (ej, ec)
print("examples OK")

# import: names matched to the dictionary, a misspelling left out, watch_under returned
mfm._Dictionary.cache = mfm._Dictionary(["Baby Angel Wings", "Angel Halo", "White Beanie",
                                         "Blue Sauna Robe", "Steel Pride"])
entries, _ = parse_json([
    {"item": "baby angel wings", "typical": "38K", "range": "35K - 40K", "total_sales": 678},
    {"item": "Angle Halo", "typical": "52K"},                                    # misspelled
    {"item": "WHITE BEANIE", "typical": "12K", "watch_under": "10K"},
    {"item": "Blue Sauna Robe", "range": "160K - 200K"},
])
res = mfm.import_mesowatch(con, entries)
assert res["imported"] == 3, res
assert [n for n, _ in res["unknown"]] == ["Angle Halo"], res
assert res["unknown"][0][1] in (None, "Angel Halo"), res
assert res["watch"] == [("White Beanie", 10000)], res
assert mfm.mesowatch_info(con, "Angle Halo") is None and mfm.mesowatch_info(con, "Angel Halo") is None
assert mfm.mesowatch_info(con, "baby angel wings") is None
baw = mfm.mesowatch_info(con, "Baby Angel Wings")
assert (baw["typical"], baw["low"], baw["high"], baw["total_sales"], baw["source"]) == \
    (38000, 35000, 40000, 678, "MesoWatch"), baw
assert baw["updated"][:10] == mfm.utc_now()[:10], baw
print("import OK")

# market_rate: range + typical, range only, typical only, stale
got, how = mfm.market_rate(con, "Baby Angel Wings", cfg)
assert isinstance(got, mfm.MarketRange) and (got.low, got.high, int(got)) == (35000, 40000, 38000), got
assert how.startswith("MesoWatch") and mfm.fmt(got) == "35,000–40,000", (how, mfm.fmt(got))
assert [mfm.verdict(p, got, 15)[0] for p in (34999, 35000, 40000, 40001)] == ["DEAL", "fair", "fair", "HIGH"]
got, _ = mfm.market_rate(con, "Blue Sauna Robe", cfg)
assert isinstance(got, mfm.MarketRange) and int(got) == 180000, got        # midpoint
got, how = mfm.market_rate(con, "White Beanie", cfg)
assert got == 12000 and not isinstance(got, mfm.MarketRange) and how.startswith("MesoWatch"), (got, how)
assert [mfm.verdict(p, got, 15)[0] for p in (10000, 12000, 14000)] == ["DEAL", "fair", "HIGH"]
con.execute("UPDATE mesowatch SET updated = '2000-01-01T00:00:00Z' WHERE item = 'Baby Angel Wings'")
got, how = mfm.market_rate(con, "Baby Angel Wings", cfg)
assert got is None and not how.startswith("MesoWatch"), (got, how)     # no sightings of your own
print("market_rate OK")

# set_range keeps what MesoWatch said; clear_range drops the range
mfm.set_range(con, "White Beanie", 11000, 13000)
wb = mfm.mesowatch_info(con, "White Beanie")
assert (wb["typical"], wb["low"], wb["high"]) == (12000, 11000, 13000), wb
got, _ = mfm.market_rate(con, "White Beanie", cfg)
assert isinstance(got, mfm.MarketRange) and int(got) == 12000, got
mfm.clear_range(con, "White Beanie")
got, _ = mfm.market_rate(con, "White Beanie", cfg)
assert not isinstance(got, mfm.MarketRange), got

# with no dictionary loaded, every name counts as known
mfm._Dictionary.cache = None
res = mfm.import_mesowatch(con, [{"item": "Totally New Item", "typical": 5, "low": None, "high": None,
                                  "volume": None, "total_volume": None, "total_sales": None,
                                  "change_24h": None, "watch_under": None}])
assert res["imported"] == 1 and not res["unknown"], res
assert mfm.mesowatch_info(con, "Totally New Item")["typical"] == 5
print("mesowatch OK")

# the 24h change: a percent however it's written, under any spelling of its name,
# stored and kept; an older mesowatch table gets the column
assert [mfm.parse_percent(v) for v in ("+4.2%", "-12%", "▼ 3.5%", 4.2, "n/a")] == [4.2, -12.0, -3.5, 4.2, None]
assert {mfm._mw_field(k) for k in ("24h", "24h Change", "change24h", "Change24H", "24 Hour Change")} == {"change_24h"}
ex, probs = mfm.parse_mesowatch(ROOT / "docs" / "mesowatch-import-example.json")
assert not probs and by_item(ex)["Steel Pride"]["change_24h"] == -12.0 and by_item(ex)["White Beanie"]["change_24h"] is None
bad, probs = parse_json([{"item": "Angel Halo", "24h": "lots"}])
assert not bad and "24h change" in probs[0][1], probs
con24 = mfm.db()
mfm._Dictionary.cache = None
mfm.import_mesowatch(con24, [dict(e, item="Baby Angel Wings") for e in ex[:1]])
assert mfm.mesowatch_info(con24, "Baby Angel Wings")["change_24h"] == 4.2
print("24h change OK")

# MesoWatch's own names: "(F)" versions and curly quotes are the plain item; a scroll
# without its grade is listed apart, not suggested as one grade; MesoWatch's export
# headers (Item Name, Typical Price, 24h Change, Sales Count, Volume) are understood
mfm._Dictionary.cache = mfm._Dictionary(["Red Cloth Pants", 'Black "Hit Me" Shirt', "Gloves Attack Scroll: Chaos",
                                         "Gloves Attack Scroll: Greater"])
res = mfm.import_mesowatch(mfm.db(), [{"item": n, "typical": 1000} for n in
                                      ("Red Cloth Pants (F)", "Black “Hit Me” Shirt", "Gloves Attack Scroll")])
assert res["imported"] == 2 and res["ungraded"] == ["Gloves Attack Scroll"] and not res["unknown"], res
assert {mfm._mw_field(k) for k in ("Item Name", "Typical Price", "24h Change", "Sales Count", "Volume")} == \
    {"item", "typical", "change_24h", "total_sales", "volume"}
print("mesowatch names OK")
