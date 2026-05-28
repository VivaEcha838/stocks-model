from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .client import fetch_market_snapshot


@dataclass
class SnapshotRow:
    ticker: str
    close: float
    volume: float
    prev_close: float
    prev_volume: float
    todays_change_pct: float
    open: float
    high: float
    low: float

    @property
    def volume_ratio_vs_prev(self) -> float:
        return self.volume / self.prev_volume if self.prev_volume else 0.0

    @property
    def gap_pct(self) -> float:
        return (self.open / self.prev_close - 1.0) if self.prev_close else 0.0

    @property
    def intraday_range_pct(self) -> float:
        if not self.low:
            return 0.0
        return (self.high - self.low) / self.low


@dataclass(frozen=True)
class ScreenerConfig:
    min_price: float = 1.0
    max_price: float = 10_000.0
    min_volume: float = 100_000.0
    min_dollar_volume: float = 0.0


DEFAULT_CONFIG = ScreenerConfig()


def parse_snapshot_row(t: dict[str, Any]) -> SnapshotRow | None:
    day = t.get("day") or {}
    prev = t.get("prevDay") or {}
    close = day.get("c") or 0.0
    volume = day.get("v") or 0.0
    prev_close = prev.get("c") or 0.0
    prev_volume = prev.get("v") or 0.0
    if close <= 0 or prev_close <= 0:
        return None
    ticker = t.get("ticker", "")
    if not ticker:
        return None
    return SnapshotRow(
        ticker=ticker,
        close=close,
        volume=volume,
        prev_close=prev_close,
        prev_volume=prev_volume,
        todays_change_pct=float(t.get("todaysChangePerc") or 0.0),
        open=day.get("o") or close,
        high=day.get("h") or close,
        low=day.get("l") or close,
    )


def load_market_snapshot() -> list[SnapshotRow]:
    raw = fetch_market_snapshot()
    parsed = (parse_snapshot_row(t) for t in raw)
    return [r for r in parsed if r is not None]


def _base_filter(rows: list[SnapshotRow], config: ScreenerConfig) -> list[SnapshotRow]:
    return [
        r for r in rows
        if config.min_price <= r.close <= config.max_price
        and r.volume >= config.min_volume
        and r.close * r.volume >= config.min_dollar_volume
    ]


def screen_movers(
    rows: list[SnapshotRow],
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    filtered = _base_filter(rows, config)
    ranked = sorted(filtered, key=lambda r: abs(r.todays_change_pct), reverse=True)
    return [r.ticker for r in ranked[:max_results]]


def screen_gainers(
    rows: list[SnapshotRow],
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    filtered = _base_filter(rows, config)
    ranked = sorted(filtered, key=lambda r: r.todays_change_pct, reverse=True)
    return [r.ticker for r in ranked[:max_results]]


def screen_losers(
    rows: list[SnapshotRow],
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    filtered = _base_filter(rows, config)
    ranked = sorted(filtered, key=lambda r: r.todays_change_pct)
    return [r.ticker for r in ranked[:max_results]]


def screen_high_volume(
    rows: list[SnapshotRow],
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    filtered = [r for r in _base_filter(rows, config) if r.prev_volume > 0]
    ranked = sorted(filtered, key=lambda r: r.volume_ratio_vs_prev, reverse=True)
    return [r.ticker for r in ranked[:max_results]]


def screen_gappers(
    rows: list[SnapshotRow],
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    filtered = _base_filter(rows, config)
    ranked = sorted(filtered, key=lambda r: abs(r.gap_pct), reverse=True)
    return [r.ticker for r in ranked[:max_results]]


def screen_volatile(
    rows: list[SnapshotRow],
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    filtered = _base_filter(rows, config)
    ranked = sorted(filtered, key=lambda r: r.intraday_range_pct, reverse=True)
    return [r.ticker for r in ranked[:max_results]]


SCREENERS: dict[str, Callable[[list[SnapshotRow], int, ScreenerConfig], list[str]]] = {
    "movers": screen_movers,
    "gainers": screen_gainers,
    "losers": screen_losers,
    "volume": screen_high_volume,
    "gappers": screen_gappers,
    "volatile": screen_volatile,
}


def run_screener(
    name: str,
    max_results: int = 100,
    config: ScreenerConfig = DEFAULT_CONFIG,
) -> list[str]:
    if name not in SCREENERS:
        raise ValueError(f"Unknown screener: {name}. Options: {list(SCREENERS.keys())}")
    snapshot = load_market_snapshot()
    return SCREENERS[name](snapshot, max_results, config)
