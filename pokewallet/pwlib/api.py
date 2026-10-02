"""Thin, dependency-free client for the PokeWallet API.

Responsibilities (all four are non-negotiable per PROJECT-PLAN.md):
1. Call any endpoint and return a structured result.
2. **Always** persist the raw response (JSON + a headers sidecar) under
   ``data/pokewallet/raw/<endpoint>/`` before anyone parses it.
3. Respect the free-plan rate budget (100/hour, 1000/day) and refuse to spend
   the last few requests unless explicitly forced.
4. Append every call to ``logs/ratelog.csv``.

Uses only the standard library so it runs with a plain ``uv run script.py``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from . import config
from .util import (
    append_csv_row,
    ensure_dir,
    now_ts,
    slugify,
    utc_iso,
    unique_path,
    write_json,
    write_text,
)

# Header name -> parsed-rate key.
RATE_HEADER_MAP: dict[str, str] = {
    "hour_limit": "X-RateLimit-Limit-Hour",
    "hour_remaining": "X-RateLimit-Remaining-Hour",
    "day_limit": "X-RateLimit-Limit-Day",
    "day_remaining": "X-RateLimit-Remaining-Day",
}

RATELOG_HEADER = [
    "timestamp_utc",
    "endpoint",
    "path",
    "query",
    "status",
    "remaining_hour",
    "remaining_day",
    "ok",
    "error",
]


class BudgetExhausted(RuntimeError):
    """Raised when the rate budget floor would be breached."""


class MissingApiKey(RuntimeError):
    """Raised when an authenticated call is attempted without a key."""


@dataclass
class ApiResponse:
    ok: bool
    status: int
    endpoint: str
    url: str
    params: dict
    headers: dict = field(default_factory=dict)
    data: Any = None
    text: str = ""
    rate: dict = field(default_factory=dict)
    saved_json: Path | None = None
    saved_headers: Path | None = None
    error: str | None = None

    @property
    def api_error(self) -> str | None:
        """Return the API's own error string if the body carries one."""
        if isinstance(self.data, dict) and isinstance(self.data.get("error"), str):
            return self.data["error"]
        return None

    def summary_line(self) -> str:
        r = self.rate
        rate_txt = (
            f"rate {r.get('hour_remaining', '?')}/{r.get('hour_limit', '?')}h "
            f"{r.get('day_remaining', '?')}/{r.get('day_limit', '?')}d"
        )
        return f"[{self.endpoint}] HTTP {self.status} ok={self.ok} {rate_txt}"


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_headers(status: int, url: str, headers: Mapping[str, str]) -> str:
    lines = [f"URL: {url}", f"STATUS: {status}", "", "--- response headers ---"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    return "\n".join(lines) + "\n"


class PokeWalletClient:
    """Endpoint-agnostic PokeWallet API client.

    Example::

        from pwlib.api import PokeWalletClient
        pw = PokeWalletClient()
        resp = pw.search(q="pikachu", limit=5)
        print(resp.status, resp.rate)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        save: bool = True,
        ratelog: bool = True,
        verbose: bool = True,
        min_hour: int | None = None,
        min_day: int | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.environ.get(config.API_KEY_ENV)
        self.base_url = (base_url or config.BASE_URL).rstrip("/")
        self.save = save
        self.ratelog = ratelog
        self.verbose = verbose
        self.min_hour = config.MIN_HOUR_REMAINING_DEFAULT if min_hour is None else min_hour
        self.min_day = config.MIN_DAY_REMAINING_DEFAULT if min_day is None else min_day
        self.timeout = timeout

        # Last observed budget (updated after every call).
        self.last_remaining_hour: int | None = None
        self.last_remaining_day: int | None = None
        self.calls = 0
        self.failures = 0

    # -- introspection ------------------------------------------------------
    def has_key(self) -> bool:
        return bool(self.api_key)

    def budget_status(self) -> str:
        if self.last_remaining_hour is None:
            return "budget: unknown (no call made yet)"
        return (
            f"budget: hour {self.last_remaining_hour}/{config.HOURLY_LIMIT}, "
            f"day {self.last_remaining_day}/{config.DAILY_LIMIT}"
        )

    # -- core request -------------------------------------------------------
    def request(
        self,
        endpoint: str,
        path: str,
        params: dict | None = None,
        *,
        save: bool | None = None,
        dry_run: bool = False,
        force: bool = False,
        min_hour: int | None = None,
        min_day: int | None = None,
        require_key: bool = False,
    ) -> ApiResponse:
        """Perform one GET request and persist the raw result."""
        save = self.save if save is None else save
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        url = self.base_url + path
        query = urllib.parse.urlencode(clean_params, doseq=True)
        if query:
            url += "?" + query

        if require_key and not self.has_key():
            raise MissingApiKey(
                f"{config.API_KEY_ENV} is not set; cannot call {endpoint}."
            )

        f_hour = self.min_hour if min_hour is None else min_hour
        f_day = self.min_day if min_day is None else min_day
        if not force and not dry_run:
            if self.last_remaining_hour is not None and self.last_remaining_hour <= f_hour:
                raise BudgetExhausted(
                    f"hourly budget floor {f_hour} reached "
                    f"(remaining {self.last_remaining_hour}); use --force to override."
                )
            if self.last_remaining_day is not None and self.last_remaining_day <= f_day:
                raise BudgetExhausted(
                    f"daily budget floor {f_day} reached "
                    f"(remaining {self.last_remaining_day}); use --force to override."
                )

        if dry_run:
            return ApiResponse(
                ok=True,
                status=0,
                endpoint=endpoint,
                url=url,
                params=clean_params,
                text="",
                error="dry-run (no request sent)",
            )

        headers = {
            "Accept": "application/json",
            "User-Agent": "marius-pokemonkort/pwlib (+local research)",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        req = urllib.request.Request(url, headers=headers, method="GET")
        status = 0
        body = b""
        resp_headers: dict[str, str] = {}
        error: str | None = None

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                resp_headers = dict(resp.headers.items())
                body = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = dict(exc.headers.items()) if exc.headers else {}
            body = exc.read()
            error = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            error = f"URLError: {exc.reason}"
            if self.verbose:
                print(f"[{endpoint}] network error: {error}")
            self.failures += 1
            # Still log the attempt.
            if self.ratelog:
                append_csv_row(
                    config.RATE_LOG_CSV,
                    RATELOG_HEADER,
                    [utc_iso(), endpoint, path, query, 0, "", "", False, error],
                )
            return ApiResponse(
                ok=False,
                status=0,
                endpoint=endpoint,
                url=url,
                params=clean_params,
                error=error,
            )

        text = body.decode("utf-8", errors="replace")
        try:
            data: Any = json.loads(text) if text.strip() else None
        except json.JSONDecodeError:
            data = None

        rate = {
            key: _parse_int(resp_headers.get(header))
            for key, header in RATE_HEADER_MAP.items()
        }
        if rate.get("hour_remaining") is not None:
            self.last_remaining_hour = rate["hour_remaining"]
        if rate.get("day_remaining") is not None:
            self.last_remaining_day = rate["day_remaining"]

        ok = 200 <= status < 300
        if not ok:
            self.failures += 1
        self.calls += 1

        saved_json: Path | None = None
        saved_headers: Path | None = None
        if save:
            ts = now_ts()
            stem = f"{ts}__{slugify(endpoint)}"
            if query:
                stem += "__" + slugify(query)
            raw_dir = config.RAW_DIR / slugify(endpoint)
            ensure_dir(raw_dir)
            if data is not None:
                saved_json = write_json(raw_dir / f"{stem}.json", data)
            else:
                saved_json = write_text(raw_dir / f"{stem}.txt", text)
            saved_headers = write_text(
                raw_dir / f"{stem}.headers.txt",
                _format_headers(status, url, resp_headers),
            )

        if self.ratelog:
            append_csv_row(
                config.RATE_LOG_CSV,
                RATELOG_HEADER,
                [
                    utc_iso(),
                    endpoint,
                    path,
                    query,
                    status,
                    rate.get("hour_remaining", ""),
                    rate.get("day_remaining", ""),
                    ok,
                    error or "",
                ],
            )

        result = ApiResponse(
            ok=ok,
            status=status,
            endpoint=endpoint,
            url=url,
            params=clean_params,
            headers=resp_headers,
            data=data,
            text=text,
            rate=rate,
            saved_json=saved_json,
            saved_headers=saved_headers,
            error=error,
        )
        if self.verbose:
            print(result.summary_line())
            if result.api_error:
                print(f"    api_error: {result.api_error}")
        return result

    # -- free endpoints -----------------------------------------------------
    def health(self, **kw: Any) -> ApiResponse:
        return self.request("health", "/health", **kw)

    def root(self, **kw: Any) -> ApiResponse:
        return self.request("root", "/", **kw)

    def search(
        self,
        q: str | None = None,
        page: int | None = None,
        limit: int | None = None,
        extra: dict | None = None,
        **kw: Any,
    ) -> ApiResponse:
        params: dict[str, Any] = {"q": q, "page": page, "limit": limit}
        if extra:
            params.update(extra)
        return self.request("search", "/search", params, require_key=True, **kw)

    def card(self, card_id: str, **kw: Any) -> ApiResponse:
        return self.request("card", f"/cards/{card_id}", require_key=True, **kw)

    def sets(self, **kw: Any) -> ApiResponse:
        return self.request("sets", "/sets", require_key=True, **kw)

    def set(
        self,
        set_code: str,
        page: int | None = None,
        limit: int | None = None,
        **kw: Any,
    ) -> ApiResponse:
        return self.request(
            "set",
            f"/sets/{set_code}",
            {"page": page, "limit": limit},
            require_key=True,
            **kw,
        )

    def images(self, card_id: str, **kw: Any) -> ApiResponse:
        return self.request("images", f"/images/{card_id}", require_key=True, **kw)

    # -- PRO endpoints (expected to be blocked on free, kept for the day
    #    they unlock — we still save whatever the API answers) --------------
    def prices(self, set_code: str, **kw: Any) -> ApiResponse:
        return self.request("prices", f"/prices/{set_code}", require_key=True, **kw)

    def price_history(self, card_id: str, **kw: Any) -> ApiResponse:
        return self.request(
            "price-history", f"/cards/{card_id}/price-history", require_key=True, **kw
        )

    def statistics(self, set_code: str, **kw: Any) -> ApiResponse:
        return self.request(
            "statistics", f"/sets/{set_code}/statistics", require_key=True, **kw
        )

    def trending(self, **kw: Any) -> ApiResponse:
        return self.request("trending", "/sets/trending", require_key=True, **kw)

    def completion_value(self, set_code: str, **kw: Any) -> ApiResponse:
        return self.request(
            "completion-value",
            f"/sets/{set_code}/completion-value",
            require_key=True,
            **kw,
        )

    def top_cards(self, **kw: Any) -> ApiResponse:
        return self.request("top-cards", "/analytics/top-cards", require_key=True, **kw)
