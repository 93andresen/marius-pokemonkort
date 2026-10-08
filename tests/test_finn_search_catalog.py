#!/usr/bin/env python3
"""Offline tests for catalog wiring + registry delta in ``finn/finn_search.py``.

No network: everything is exercised through the pure helpers and the
side-effect-free ``--dry-run`` path.  Run with:

    uv run tests/test_finn_search_catalog.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "finn"))

import finn_search  # noqa: E402
import finn_searches  # noqa: E402


def _run_main(argv):
    """Run finn_search.main(argv), capturing stdout; return (rc, output)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = finn_search.main(argv)
    return rc, buf.getvalue()


class JobsFromDefs(unittest.TestCase):
    def test_catalog_jobs_have_params_and_sorts(self) -> None:
        defs = finn_searches.search_defs("all")
        self.assertGreater(len(defs), 0)
        jobs = finn_search.jobs_from_defs(
            defs, cli_sorts=["PUBLISHED_DESC"], cli_max_pages=1, cli_extra=[]
        )
        self.assertEqual(len(jobs), len(defs), "one job per catalog definition")
        for job in jobs:
            self.assertTrue(job["query"])
            self.assertGreaterEqual(job["max_pages"], 1)
            self.assertGreaterEqual(len(job["sorts"]), 1)
            p = dict(job["params"])
            self.assertEqual(p.get("sub_category"), "1.86.285", job["id"])
            self.assertEqual(p.get("product_category"), "2.86.285.396", job["id"])
        print(f"[catalog] {len(jobs)} jobs from {len(defs)} defs")

    def test_adhoc_falls_back_to_cli(self) -> None:
        defs = [{"id": "query-x", "kind": "query", "label": "x", "query": "pokemon kort",
                 "tier": None, "params": {}, "sorts": None, "max_pages": None}]
        jobs = finn_search.jobs_from_defs(
            defs, cli_sorts=["RELEVANCE"], cli_max_pages=3, cli_extra=[("foo", "bar")]
        )
        self.assertEqual(jobs[0]["sorts"], ["RELEVANCE"])
        self.assertEqual(jobs[0]["max_pages"], 3)
        self.assertIn(("foo", "bar"), jobs[0]["params"])

    def test_catalog_defs_keep_their_own_sorts(self) -> None:
        defs = [{"id": "set-jungle", "kind": "set", "label": "Jungle", "query": "Jungle",
                 "tier": 1, "params": {"category": "0.86"},
                 "sorts": ["PUBLISHED_DESC"], "max_pages": 2}]
        jobs = finn_search.jobs_from_defs(
            defs, cli_sorts=["RELEVANCE"], cli_max_pages=9, cli_extra=[]
        )
        self.assertEqual(jobs[0]["sorts"], ["PUBLISHED_DESC"], "def sorts win")
        self.assertEqual(jobs[0]["max_pages"], 2, "def max_pages wins")


class BuildUrl(unittest.TestCase):
    def test_params_and_paging(self) -> None:
        u = finn_search.build_url("pokemon kort", "RELEVANCE", 1, [("sub_category", "1.86.285")])
        self.assertIn("q=pokemon+kort", u)
        self.assertIn("sort=RELEVANCE", u)
        self.assertIn("sub_category=1.86.285", u)
        self.assertNotIn("page=1", u)
        u2 = finn_search.build_url("pokemon kort", "RELEVANCE", 2, [])
        self.assertIn("page=2", u2)


class ComputeDelta(unittest.TestCase):
    def test_new_still_active_gone(self) -> None:
        d = finn_search.compute_delta({"a", "b"}, {"b", "c"})
        self.assertEqual(d["new"], ["c"])
        self.assertEqual(d["still_active"], ["b"])
        self.assertEqual(d["gone"], ["a"])

    def test_no_change(self) -> None:
        d = finn_search.compute_delta({"a"}, {"a"})
        self.assertEqual(d["new"], [])
        self.assertEqual(d["still_active"], ["a"])
        self.assertEqual(d["gone"], [])

    def test_partition(self) -> None:
        d = finn_search.compute_delta({"a", "b", "c"}, {"b", "d"})
        # every element appears in exactly one bucket; union == inputs; new+gone disjoint
        self.assertEqual(set(d["new"]), {"d"})
        self.assertEqual(set(d["still_active"]), {"b"})
        self.assertEqual(set(d["gone"]), {"a", "c"})
        for group in ("new", "still_active", "gone"):
            self.assertEqual(len(d[group]), len(set(d[group])), "no duplicates")


class DryRunEndToEnd(unittest.TestCase):
    def test_search_set_dry_run_expands_catalog(self) -> None:
        rc, out = _run_main(["--search-set", "--dry-run"])
        self.assertEqual(rc, 0)
        defs = finn_searches.search_defs("all")
        expected = sum(d["max_pages"] * len(d["sorts"]) for d in defs)
        self.assertIn(f"planned_pages={expected}", out)
        self.assertIn("files_written=0", out)
        self.assertIn("product_category=2.86.285.396", out)
        self.assertIn("[set-jungle | Jungle |", out)
        print(f"[dry-run] planned_pages={expected} (from {len(defs)} defs)")

    def test_kind_filter_limits_jobs(self) -> None:
        rc, out = _run_main(["--search-set", "--kind", "card", "--dry-run"])
        self.assertEqual(rc, 0)
        cards = finn_searches.search_defs("card")
        expected = sum(d["max_pages"] * len(d["sorts"]) for d in cards)
        self.assertIn(f"jobs={len(cards)}", out)
        self.assertIn(f"planned_pages={expected}", out)

    def test_dry_run_writes_nothing(self) -> None:
        root = REPO_ROOT / "data" / "finn"
        subs = ("registry", "_log", "searches", "filters")

        def snapshot():
            out = []
            for s in subs:
                d = root / s
                if d.exists():
                    out += sorted(str(p) for p in d.rglob("*"))
            return out

        before = snapshot()
        rc, _ = _run_main(["--search-set", "--kind", "broad", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(before, snapshot(), "dry-run must not create/modify any files")


if __name__ == "__main__":
    unittest.main(verbosity=2)
