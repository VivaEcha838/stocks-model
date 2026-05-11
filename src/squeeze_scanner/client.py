from __future__ import annotations

from typing import Any

import requests

from .config import API_KEY, BASE_URL, HTTP_TIMEOUT_SECONDS


class APIError(RuntimeError):
    pass


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not API_KEY:
        raise APIError("SQUEEZE_API_KEY is not set — copy .env.example to .env")

    params = dict(params or {})
    params["apiKey"] = API_KEY
    url = f"{BASE_URL}{path}"

    try:
        r = requests.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
        r.raise_for_status()
    except requests.RequestException as e:
        raise APIError(f"GET {url} failed: {e}") from e

    return r.json()


def fetch_daily_bars(ticker: str, start: str, end: str) -> list[dict[str, Any]]:
    path = f"/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
    data = _get(path, {"adjusted": "true", "sort": "asc", "limit": 5000})
    return data.get("results") or []


def fetch_short_interest(ticker: str) -> dict[str, Any]:
    try:
        data = _get("/stocks/v1/short-interest", {"ticker": ticker, "limit": 1})
    except APIError:
        return {}
    results = data.get("results") or []
    return results[0] if results else {}


def fetch_float(ticker: str) -> dict[str, Any]:
    try:
        data = _get(f"/v3/reference/tickers/{ticker}")
    except APIError:
        return {}
    res = data.get("results") or {}
    if not res:
        return {}
    shares = res.get("share_class_shares_outstanding") or res.get("weighted_shares_outstanding")
    return {
        "free_float": shares,
        "free_float_percent": None,
    }
