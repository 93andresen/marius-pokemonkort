#!/usr/bin/env python3
"""Probe: why does finn_matcher's query cache not hit on a second run?

Loads the matcher's cache through its own ``load_cache`` and reports the keys,
ages, and whether the *planned* query normalises to a cached key. Read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3] / "finn"))            # repo finn/
sys.path.insert(0, str(_HERE.parents[3] / "pokewallet"))      # repo pokewallet/

import finn_matcher as fm  # noqa: E402
from pwlib import sets as setslib  # noqa: E402

print("CACHE_JSONL      :", fm.CACHE_JSONL)
print("cache exists     :", fm.CACHE_JSONL.exists())
print("cache size bytes :", fm.CACHE_JSONL.stat().st_size if fm.CACHE_JSONL.exists() else "-")

cache = fm.load_cache()
print("loaded keys (%d):" % len(cache), list(cache.keys()))
for k, rec in cache.items():
    print("  key=%r  fetched_at=%r  age_h=%s  count=%s"
          % (k, rec.get("fetched_at"), fm.cache_age_hours(rec), rec.get("count")))

for q in ["Psychic Energy Base Set 101", "Psychic Energy Base Set"]:
    key = setslib.normalize_name(q)
    print("query %r -> key %r  in_cache=%s" % (q, key, key in cache))
