from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from .client import APIError, fetch_daily_bars, fetch_float, fetch_short_interest
from .config import MAX_WORKERS
from .metrics import RawFeatures, SqueezeMetrics
from .scoring import score_features


MIN_BARS = 30


def _default_window() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=200)
    return start.isoformat(), end.isoformat()


def scan_ticker(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    catalyst_score: float = 0.0,
    catalyst_tag: str = "",
) -> SqueezeMetrics | None:
    if start is None or end is None:
        start, end = _default_window()

    bars = fetch_daily_bars(ticker, start, end)
    if len(bars) < MIN_BARS:
        return None

    closes = [b["c"] for b in bars]
    vols = [b["v"] for b in bars]

    close = closes[-1]
    volume = vols[-1]
    avg_volume_30d = statistics.mean(vols[-30:])
    high_20d = max(closes[-20:])
    vol_ratio = volume / avg_volume_30d if avg_volume_30d else 0.0
    breakout_pct = (close / high_20d - 1.0) if high_20d else 0.0

    si = fetch_short_interest(ticker)
    fl = fetch_float(ticker)

    short_interest_shares = float(si.get("short_interest") or 0)
    free_float_shares = fl.get("free_float")
    free_float_percent = fl.get("free_float_percent")

    short_pct_float = None
    if free_float_shares and float(free_float_shares) > 0:
        short_pct_float = 100.0 * short_interest_shares / float(free_float_shares)

    days_to_cover = (
        short_interest_shares / avg_volume_30d if avg_volume_30d else None
    )

    raw = RawFeatures(
        short_pct_float=short_pct_float,
        days_to_cover=days_to_cover,
        volume_ratio=vol_ratio,
        breakout_pct=breakout_pct,
        float_tightness_pct=free_float_percent if free_float_percent is not None else 100.0,
        catalyst_score=catalyst_score,
    )

    score, labels = score_features(raw)

    return SqueezeMetrics(
        ticker=ticker,
        close=close,
        volume=volume,
        avg_volume_30d=avg_volume_30d,
        high_20d=high_20d,
        short_interest_shares=short_interest_shares,
        free_float_shares=free_float_shares,
        free_float_percent=free_float_percent,
        short_pct_float=short_pct_float,
        days_to_cover=days_to_cover,
        vol_ratio=vol_ratio,
        breakout_pct=breakout_pct,
        catalyst_tag=catalyst_tag,
        score=score,
        labels=labels,
    )


def scan_universe(
    tickers: list[str],
    start: str | None = None,
    end: str | None = None,
    catalysts: dict[str, tuple[float, str]] | None = None,
    max_workers: int = MAX_WORKERS,
) -> list[SqueezeMetrics]:
    catalysts = catalysts or {}
    out: list[SqueezeMetrics] = []

    def _job(t: str) -> SqueezeMetrics | None:
        cs, tag = catalysts.get(t, (0.0, ""))
        return scan_ticker(t, start, end, catalyst_score=cs, catalyst_tag=tag)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_job, t): t for t in tickers}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                m = fut.result()
                if m is not None:
                    out.append(m)
            except APIError as e:
                print(f"[skip] {t}: {e}")
            except Exception as e:
                print(f"[skip] {t}: unexpected {e!r}")

    return sorted(out, key=lambda m: m.score, reverse=True)
