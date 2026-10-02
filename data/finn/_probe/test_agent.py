#!/usr/bin/env python3
"""End-to-end probe for tools/local_agent.py.

Boots the real handler (same code the CLI serves) on an ephemeral 127.0.0.1
port in a background thread, then exercises every route:

    GET  /health
    GET  /
    GET  /match?heading=&price=&kode=&url=   (offline -> cache-only)
    POST /log
    GET  /history?since_days=28&match=...

No API budget is spent: the service runs with offline=True.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
sys.path.insert(0, str(_REPO / "tools"))

import local_agent as la  # noqa: E402


def _get(base: str, path: str, params: dict | None = None) -> tuple[int, object]:
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = base + path + qs
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def _post(base: str, path: str, obj: dict) -> tuple[int, object]:
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main() -> int:
    service = la.MatcherService(offline=True, cache_hours=24.0, max_candidates=5,
                                fx={"USD": 11.5, "EUR": 12.5})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), la._make_handler(service))
    port = int(httpd.server_address[1])
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print("=" * 88)
    print(f"probe: agent bound on {base}  (offline={service.offline})")
    print(f"probe: index loaded = {bool(service.index)}")
    ok = 0
    total = 0

    def check(label: str, cond: bool, extra: str = "") -> None:
        nonlocal ok, total
        total += 1
        ok += 1 if cond else 0
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}{(' :: ' + extra) if extra else ''}")

    # 1. /health
    status, body = _get(base, "/health")
    check("GET /health 200", status == 200, f"status={status}")
    check("health.ok", isinstance(body, dict) and body.get("ok") is True,
          f"body={body if not isinstance(body, dict) else {k: body[k] for k in list(body)[:4]}}")

    # 2. /  (index)
    status, body = _get(base, "/")
    check("GET / 200", status == 200)
    check("index lists /match", isinstance(body, dict) and any("/match" in e for e in body.get("endpoints", [])),
          f"endpoints={body.get('endpoints') if isinstance(body, dict) else body}")

    # 3. /match  (offline; heading mirrors the validated live test)
    status, body = _get(base, "/match", {
        "heading": "Psychic Energy #101 Base Set (1999)",
        "price": "200", "kode": "999000111", "url": "https://www.finn.no/item/999000111",
    })
    check("GET /match 200", status == 200, f"status={status}")
    if isinstance(body, dict):
        check("match returns parsed", isinstance(body.get("parsed"), dict),
              f"parsed={body.get('parsed')}")
        check("match has candidates list", isinstance(body.get("candidates"), list),
              f"n={len(body.get('candidates') or [])}")
        check("match offline spent 0 calls", body.get("calls_spent") == 0,
              f"calls_spent={body.get('calls_spent')}")
        print(f"        -> parsed={body.get('parsed')}")
        print(f"        -> queries={body.get('queries')}")
        print(f"        -> best={body.get('best')}")
        print(f"        -> value={body.get('value')}")
    else:
        check("match returns dict", False, f"body={body}")

    # 4. POST /log
    status, body = _post(base, "/log", {
        "heading": "Psychic Energy #101 Base Set (1999)", "finn_kode": "999000111",
        "finn_price_nok": 200, "url": "https://www.finn.no/item/999000111",
        "value": {"est_nok": 150, "native": 13.0, "currency": "USD"},
    })
    check("POST /log 200", status == 200, f"status={status}")
    check("log echoes ok", isinstance(body, dict) and body.get("ok") is True, f"body={body}")

    # 5. GET /history  (find the just-logged ad)
    status, body = _get(base, "/history", {"since_days": 28, "match": "psychic"})
    check("GET /history 200", status == 200, f"status={status}")
    if isinstance(body, dict):
        check("history found logged ad", body.get("count", 0) >= 1,
              f"count={body.get('count')}")
        recs = body.get("records") or []
        if recs:
            print(f"        -> newest: {recs[0].get('heading')!r} @ {recs[0].get('viewed_at')}")

    # 6. 404 route
    status, _ = _get(base, "/nope")
    check("unknown route 404", status == 404, f"status={status}")

    httpd.shutdown()
    print("-" * 88)
    print(f"probe: {ok}/{total} checks passed")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
