#!/usr/bin/env python3
"""Local HTTP helper the finn.no userscript calls.

Runs a tiny ``127.0.0.1``-only server that turns a FINN listing (heading + price)
into a PokeWallet price overlay via :mod:`finn_matcher`, and appends every viewed
ad to the append-only history log (:mod:`history_logger`).

Endpoints (all JSON, CORS-enabled so ``finn.no`` pages may call it):

* ``GET  /health``  → ``{ok, version, offline, budget}``
* ``GET  /match``   → query params ``heading`` (required), ``price``, ``kode``,
  ``url``, ``status``, ``location`` → the matcher's overlay payload.
* ``POST /log``     → body = viewed-ad JSON → appended to the history log.
* ``GET  /history`` → params ``since_days``/``since_hours``, ``match``, ``kode``,
  ``limit`` → previously viewed ads (e.g. *"all Pichu's, last 4 weeks"*).

Security: binds to ``127.0.0.1`` only; makes no outbound calls beyond the
PokeWallet API (never finn.no). Budget is respected — if the free hourly floor is
hit, ``/match`` transparently falls back to the cache-only path.

Run::

    uv run tools/local_agent.py            # live (uses API budget, cache-first)
    uv run tools/local_agent.py --offline   # cache-only, never spends a call
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "finn"))   # repo finn/ -> finnlib, finn_matcher
sys.path.insert(0, str(_HERE.parent))                 # tools/  -> history_logger

import finn_matcher as fm  # noqa: E402
import history_logger as hl  # noqa: E402

VERSION = "local_agent/1.0.0"
DEFAULT_PORT = 8765


class MatcherService:
    """Holds the (expensive) set index + query cache + API client across requests."""

    def __init__(self, *, offline: bool, cache_hours: float, max_candidates: int, fx: dict[str, float]) -> None:
        self.offline = offline
        self.cache_hours = cache_hours
        self.max_candidates = max_candidates
        self.fx = fx
        self.lock = threading.Lock()
        self.index = fm._load_index()
        self.cache = fm.load_cache()
        self.client: Any = None
        if not self.offline:
            self.client = fm.PokeWalletClient(verbose=True)
            if not self.client.has_key():
                print(f"WARN: {fm.pwconfig.API_KEY_ENV} not set → running cache-only (offline).")
                self.client = None
                self.offline = True

    def _run(self, listing: dict[str, Any], *, offline: bool) -> dict[str, Any]:
        return fm.match_listing(
            listing, client=(None if offline else self.client), index=self.index,
            cache=self.cache, cache_hours=self.cache_hours, offline=offline, fx=self.fx,
            max_queries=2, max_candidates=self.max_candidates,
        )

    def match(self, listing: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            try:
                return self._run(listing, offline=self.offline)
            except (fm.BudgetExhausted, fm.MissingApiKey) as exc:
                ov = self._run(listing, offline=True)
                ov["budget_note"] = f"budget guard: {exc}"
                return ov

    def budget(self) -> str:
        if self.client is None:
            return "offline (cache-only)"
        return self.client.budget_status()


def _make_handler(service: MatcherService):
    class Handler(BaseHTTPRequestHandler):
        server_version = VERSION

        # -- helpers ---------------------------------------------------------
        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, obj: Any, status: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - matches stdlib signature
            # Name MUST be ``format`` to match BaseHTTPRequestHandler.log_message.
            print(f"[agent] {self.address_string()} {format % args}")

        # -- routing ---------------------------------------------------------
        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            route = parsed.path.rstrip("/") or "/"

            if route == "/health":
                self._json({"ok": True, "version": VERSION,
                            "offline": service.offline, "budget": service.budget()})
                return

            if route == "/":
                self._json({
                    "service": VERSION,
                    "endpoints": ["/health", "/match?heading=…&price=…&kode=…&url=…",
                                  "POST /log", "/history?since_days=…&match=…"],
                })
                return

            if route == "/match":
                heading = (params.get("heading") or "").strip()
                if not heading:
                    self._json({"error": "missing required 'heading' param"}, 400)
                    return
                listing = {
                    "heading": heading,
                    "finn_kode": params.get("kode") or None,
                    "url": params.get("url") or None,
                    "finn_price_nok": _to_int(params.get("price")),
                    "status": params.get("status") or None,
                    "location": params.get("location") or None,
                }
                print(f"[agent] /match {heading!r} price={listing['finn_price_nok']} kode={listing['finn_kode']}")
                self._json(service.match(listing))
                return

            if route == "/history":
                since_days = _to_float(params.get("since_days"))
                since_hours = _to_float(params.get("since_hours"))
                if since_hours is None and since_days is not None:
                    since_hours = since_days * 24.0
                rows = hl.read_history(
                    since_hours=since_hours,
                    match=params.get("match") or None,
                    kode=params.get("kode") or None,
                    limit=_to_int(params.get("limit")) or 0,
                )
                self._json({"count": len(rows), "records": rows})
                return

            self._json({"error": f"unknown route {route!r}"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            length = _to_int(self.headers.get("Content-Length")) or 0
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                body = json.loads(raw or "{}")
            except json.JSONDecodeError as exc:
                self._json({"error": f"invalid JSON body: {exc}"}, 400)
                return

            if route == "/log":
                rec = hl.log_view(body if isinstance(body, dict) else {"value": body})
                print(f"[agent] /log kode={rec.get('finn_kode')} heading={rec.get('heading')!r}")
                self._json({"ok": True, "logged": rec})
                return

            self._json({"error": f"unknown route {route!r}"}, 404)

    return Handler


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local FINN→PokeWallet agent for the browser userscript.")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (keep on loopback!)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--offline", action="store_true", help="cache-only; never spend an API call")
    parser.add_argument("--cache-hours", type=float, default=24.0)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--fx-usd", type=float, default=fm.FX_DEFAULTS["USD"])
    parser.add_argument("--fx-eur", type=float, default=fm.FX_DEFAULTS["EUR"])
    args = parser.parse_args(argv)

    service = MatcherService(
        offline=args.offline, cache_hours=args.cache_hours,
        max_candidates=args.max_candidates, fx={"USD": args.fx_usd, "EUR": args.fx_eur},
    )
    httpd = ThreadingHTTPServer((args.host, args.port), _make_handler(service))
    url = f"http://{args.host}:{args.port}"
    print("=" * 88)
    print(f"{VERSION} listening on {url}  (offline={service.offline})")
    print(f"  index loaded : {'yes' if service.index else 'NO'}")
    print(f"  budget       : {service.budget()}")
    print(f"  history log  : {hl.HISTORY_JSONL}")
    print("  endpoints    : /health  /match  /history  (POST /log)")
    print("  Ctrl+C to stop.")
    print("=" * 88)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[agent] shutting down.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
