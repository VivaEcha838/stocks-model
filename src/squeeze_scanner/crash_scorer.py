from __future__ import annotations

from .config import CRASH_BANDS, CRASH_WEIGHTS
from .metrics import CrashFeatures, CrashLabels
from .scoring import _band_normalize, clamp01


def score_crash(raw: CrashFeatures) -> tuple[float, CrashLabels]:
    w = CRASH_WEIGHTS
    b = CRASH_BANDS

    n_below_50 = _band_normalize(raw.close_vs_50d_ma, b.close_vs_50d_ma)
    n_below_200 = _band_normalize(raw.close_vs_200d_ma, b.close_vs_200d_ma)
    n_drawdown = _band_normalize(raw.drawdown_from_52w, b.drawdown_from_52w)
    n_distribution = _band_normalize(float(raw.distribution_day_count_20d), b.distribution_day_count)
    n_downgrades = _band_normalize(float(raw.analyst_downgrade_count_30d), b.analyst_downgrade_count)
    n_consecutive = _band_normalize(float(raw.consecutive_down_days), b.consecutive_down_days)
    n_breakdown = _band_normalize(raw.close_vs_20d_low, b.close_vs_20d_low)
    n_gap = clamp01(1.0 if raw.gap_down_recent else 0.0)

    weakness = (
        w.below_50d * n_below_50
        + w.below_200d * n_below_200
        + w.drawdown * n_drawdown
    )
    distribution = (
        w.distribution_days * n_distribution
        + w.analyst_downgrades * n_downgrades
    )
    trigger = (
        w.consecutive_down * n_consecutive
        + w.breakdown_support * n_breakdown
        + w.gap_down * n_gap
    )
    score = weakness + distribution + trigger

    reasons: list[str] = []
    if raw.close_vs_50d_ma < 0.98:
        reasons.append(f"Below 50d MA ({(raw.close_vs_50d_ma-1)*100:.1f}%)")
    if raw.close_vs_200d_ma < 0.98:
        reasons.append(f"Below 200d MA ({(raw.close_vs_200d_ma-1)*100:.1f}%)")
    if raw.drawdown_from_52w >= 0.15:
        reasons.append(f"{raw.drawdown_from_52w*100:.0f}% drawdown from 52w high")
    if raw.distribution_day_count_20d >= 3:
        reasons.append(f"{raw.distribution_day_count_20d} distribution days in last 20")
    if raw.analyst_downgrade_count_30d >= 2:
        reasons.append(f"{raw.analyst_downgrade_count_30d} analyst downgrades")
    if raw.consecutive_down_days >= 3:
        reasons.append(f"{raw.consecutive_down_days} consecutive down days")
    if raw.close_vs_20d_low <= 1.01:
        reasons.append("At or below 20d low")
    if raw.gap_down_recent:
        reasons.append("Recent gap down")

    return round(score, 2), CrashLabels(
        weakness=round(weakness, 2),
        distribution=round(distribution, 2),
        trigger=round(trigger, 2),
        risk_level=crash_risk_level(score),
        confidence=crash_confidence(score, len(reasons)),
        reasons=reasons,
    )


def crash_risk_level(score: float) -> str:
    if score >= 70:
        return "Breaking"
    if score >= 45:
        return "Weakening"
    if score >= 25:
        return "Caution"
    return "Stable"


def crash_confidence(score: float, reason_count: int) -> str:
    if score >= 60 and reason_count >= 4:
        return "High"
    if score >= 35 and reason_count >= 2:
        return "Medium"
    return "Low"
