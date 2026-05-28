from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from .client import APIError, fetch_daily_bars, fetch_float, fetch_short_interest
from .config import MAX_WORKERS
from .crash_scorer import score_crash
from .dominant import classify_dominant
from .metrics import (
    CrashFeatures,
    MarketSnapshot,
    MoonshotFeatures,
    MultiTrackMetrics,
    RawFeatures,
)
from .moonshot_scorer import score_moonshot
from .scoring import score_features


MIN_BARS = 30
DEFAULT_LOOKBACK_DAYS = 400


def _default_window() -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    return start.isoformat(), end.isoformat()


def _build_snapshot(bars: list[dict]) -> MarketSnapshot:
    closes = [b["c"] for b in bars]
    vols = [b["v"] for b in bars]
    opens = [b["o"] for b in bars]

    close = closes[-1]
    volume = vols[-1]
    avg_vol_30d = statistics.mean(vols[-30:])

    high_20d = max(closes[-20:])
    low_20d = min(closes[-20:])
    high_52w = max(closes[-252:]) if len(closes) >= 252 else max(closes)

    sma_50d = statistics.mean(closes[-50:]) if len(closes) >= 50 else statistics.mean(closes)
    sma_200d = statistics.mean(closes[-200:]) if len(closes) >= 200 else statistics.mean(closes)

    vol_ratio = volume / avg_vol_30d if avg_vol_30d else 0.0
    breakout_pct = (close / high_20d - 1.0) if high_20d else 0.0
    drawdown_from_52w = (high_52w - close) / high_52w if high_52w else 0.0
    close_vs_50d_ma = close / sma_50d if sma_50d else 1.0
    close_vs_200d_ma = close / sma_200d if sma_200d else 1.0
    close_vs_20d_low = close / low_20d if low_20d else 1.0

    momentum_5d = (close / closes[-6] - 1.0) if len(closes) >= 6 and closes[-6] else 0.0

    if len(vols) >= 35:
        recent_5_avg = statistics.mean(vols[-5:])
        baseline_avg = statistics.mean(vols[-35:-5])
        volume_trend_5d = recent_5_avg / baseline_avg if baseline_avg else 0.0
    else:
        volume_trend_5d = vol_ratio

    consecutive_down = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            consecutive_down += 1
        else:
            break

    distribution_days = 0
    threshold = avg_vol_30d * 1.25
    start_i = max(1, len(closes) - 20)
    for i in range(start_i, len(closes)):
        if closes[i] < closes[i - 1] and vols[i] > threshold:
            distribution_days += 1

    gap_up_recent = False
    gap_down_recent = False
    look_back = min(5, len(bars) - 1)
    for i in range(len(bars) - look_back, len(bars)):
        prev_close = closes[i - 1] if i > 0 else None
        if prev_close:
            gap = opens[i] / prev_close - 1.0
            if gap > 0.03:
                gap_up_recent = True
            if gap < -0.03:
                gap_down_recent = True

    tight_base = False
    if len(closes) >= 11:
        prior_10 = closes[-11:-1]
        prior_range_pct = (max(prior_10) - min(prior_10)) / close if close else 0.0
        tight_base = prior_range_pct < 0.08

    max_single_day_move = 0.0
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            move = abs(closes[i] / closes[i - 1] - 1.0)
            if move > max_single_day_move:
                max_single_day_move = move
    has_data_anomaly = max_single_day_move > 0.70

    return MarketSnapshot(
        close=close,
        volume=volume,
        avg_volume_30d=avg_vol_30d,
        high_20d=high_20d,
        high_52w=high_52w,
        low_20d=low_20d,
        sma_50d=sma_50d,
        sma_200d=sma_200d,
        vol_ratio=vol_ratio,
        breakout_pct=breakout_pct,
        drawdown_from_52w=drawdown_from_52w,
        close_vs_50d_ma=close_vs_50d_ma,
        close_vs_200d_ma=close_vs_200d_ma,
        close_vs_20d_low=close_vs_20d_low,
        momentum_5d=momentum_5d,
        volume_trend_5d=volume_trend_5d,
        consecutive_down_days=consecutive_down,
        distribution_day_count_20d=distribution_days,
        gap_up_recent=gap_up_recent,
        gap_down_recent=gap_down_recent,
        tight_base=tight_base,
        has_data_anomaly=has_data_anomaly,
        max_single_day_move_pct=max_single_day_move,
    )


def scan_ticker(
    ticker: str,
    start: str | None = None,
    end: str | None = None,
    catalyst_score: float = 0.0,
    catalyst_tag: str = "",
    analyst_upgrade_count_30d: int = 0,
    analyst_downgrade_count_30d: int = 0,
) -> MultiTrackMetrics | None:
    if start is None or end is None:
        start, end = _default_window()

    bars = fetch_daily_bars(ticker, start, end)
    if len(bars) < MIN_BARS:
        return None

    snap = _build_snapshot(bars)

    si = fetch_short_interest(ticker)
    fl = fetch_float(ticker)

    short_interest_shares = float(si.get("short_interest") or 0)
    free_float_shares = fl.get("free_float")
    free_float_percent = fl.get("free_float_percent")

    short_pct_float = None
    if free_float_shares and float(free_float_shares) > 0:
        short_pct_float = 100.0 * short_interest_shares / float(free_float_shares)

    days_to_cover = (
        short_interest_shares / snap.avg_volume_30d if snap.avg_volume_30d else None
    )

    market_cap_usd = None
    if free_float_shares:
        market_cap_usd = float(free_float_shares) * snap.close

    squeeze_raw = RawFeatures(
        short_pct_float=short_pct_float,
        days_to_cover=days_to_cover,
        volume_ratio=snap.vol_ratio,
        breakout_pct=snap.breakout_pct,
        float_tightness_pct=free_float_percent if free_float_percent is not None else 100.0,
        catalyst_score=catalyst_score,
    )
    squeeze_score_val, squeeze_labels = score_features(squeeze_raw)

    moonshot_raw = MoonshotFeatures(
        close_vs_52w_high=snap.close / snap.high_52w if snap.high_52w else 0.0,
        market_cap_usd=market_cap_usd,
        close_vs_200d_ma=snap.close_vs_200d_ma,
        catalyst_score=catalyst_score,
        analyst_upgrade_count_30d=analyst_upgrade_count_30d,
        volume_trend_5d=snap.volume_trend_5d,
        momentum_5d=snap.momentum_5d,
        close_vs_50d_ma=snap.close_vs_50d_ma,
        tight_base=snap.tight_base,
    )
    moonshot_score_val, moonshot_labels = score_moonshot(moonshot_raw)

    crash_raw = CrashFeatures(
        close_vs_50d_ma=snap.close_vs_50d_ma,
        close_vs_200d_ma=snap.close_vs_200d_ma,
        drawdown_from_52w=snap.drawdown_from_52w,
        distribution_day_count_20d=snap.distribution_day_count_20d,
        analyst_downgrade_count_30d=analyst_downgrade_count_30d,
        consecutive_down_days=snap.consecutive_down_days,
        close_vs_20d_low=snap.close_vs_20d_low,
        gap_down_recent=snap.gap_down_recent,
    )
    crash_score_val, crash_labels = score_crash(crash_raw)

    if snap.has_data_anomaly:
        anomaly_msg = (
            f"WARN: possible data anomaly "
            f"(single-day move of {snap.max_single_day_move_pct*100:.0f}% in history)"
        )
        squeeze_labels.reasons.append(anomaly_msg)
        moonshot_labels.reasons.append(anomaly_msg)
        crash_labels.reasons.append(anomaly_msg)

    dominant, action = classify_dominant(
        squeeze_score_val,
        squeeze_labels.risk_level,
        moonshot_score_val,
        moonshot_labels.risk_level,
        crash_score_val,
        crash_labels.risk_level,
        squeeze_reasons=squeeze_labels.reasons,
        moonshot_reasons=moonshot_labels.reasons,
        crash_reasons=crash_labels.reasons,
    )

    return MultiTrackMetrics(
        ticker=ticker,
        close=snap.close,
        volume=snap.volume,
        avg_volume_30d=snap.avg_volume_30d,
        high_20d=snap.high_20d,
        high_52w=snap.high_52w,
        sma_50d=snap.sma_50d,
        sma_200d=snap.sma_200d,
        market_cap_usd=market_cap_usd,
        short_pct_float=short_pct_float,
        days_to_cover=days_to_cover,
        free_float_percent=free_float_percent,
        vol_ratio=snap.vol_ratio,
        breakout_pct=snap.breakout_pct,
        drawdown_from_52w=snap.drawdown_from_52w,
        catalyst_tag=catalyst_tag,
        squeeze_score=squeeze_score_val,
        squeeze_labels=squeeze_labels,
        moonshot_score=moonshot_score_val,
        moonshot_labels=moonshot_labels,
        crash_score=crash_score_val,
        crash_labels=crash_labels,
        dominant=dominant,
        action=action,
    )


def scan_universe(
    tickers: list[str],
    start: str | None = None,
    end: str | None = None,
    catalysts: dict[str, tuple[float, str]] | None = None,
    upgrades: dict[str, int] | None = None,
    downgrades: dict[str, int] | None = None,
    max_workers: int = MAX_WORKERS,
) -> list[MultiTrackMetrics]:
    catalysts = catalysts or {}
    upgrades = upgrades or {}
    downgrades = downgrades or {}
    out: list[MultiTrackMetrics] = []

    def _job(t: str) -> MultiTrackMetrics | None:
        cs, tag = catalysts.get(t, (0.0, ""))
        up = upgrades.get(t, 0)
        down = downgrades.get(t, 0)
        return scan_ticker(
            t, start, end,
            catalyst_score=cs,
            catalyst_tag=tag,
            analyst_upgrade_count_30d=up,
            analyst_downgrade_count_30d=down,
        )

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

    return sorted(
        out,
        key=lambda m: max(m.squeeze_score, m.moonshot_score, m.crash_score),
        reverse=True,
    )
