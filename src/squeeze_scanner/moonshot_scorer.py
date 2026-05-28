from __future__ import annotations

from .config import MOONSHOT_BANDS, MOONSHOT_WEIGHTS
from .metrics import MoonshotFeatures, MoonshotLabels
from .scoring import _band_normalize, _peaked_normalize, clamp01


BREAKOUT_NO_BASE_PENALTY = 0.5
BREAKOUT_AT_HIGH_THRESHOLD = 0.95


def score_moonshot(raw: MoonshotFeatures) -> tuple[float, MoonshotLabels]:
    w = MOONSHOT_WEIGHTS
    b = MOONSHOT_BANDS

    n_breakout = _band_normalize(raw.close_vs_52w_high, b.close_vs_52w_high)
    if raw.close_vs_52w_high >= BREAKOUT_AT_HIGH_THRESHOLD and not raw.tight_base:
        n_breakout *= BREAKOUT_NO_BASE_PENALTY

    n_smallcap = _band_normalize(
        raw.market_cap_usd if raw.market_cap_usd is not None else 50_000_000_000.0,
        b.market_cap_usd,
    )
    n_above_200 = _peaked_normalize(raw.close_vs_200d_ma, b.close_vs_200d_ma)
    n_catalyst = clamp01(raw.catalyst_score)
    n_upgrades = _band_normalize(float(raw.analyst_upgrade_count_30d), b.analyst_upgrade_count)
    n_vol_trend = _band_normalize(raw.volume_trend_5d, b.volume_trend_5d)
    n_momentum = _band_normalize(raw.momentum_5d, b.momentum_5d)
    n_above_50 = _band_normalize(raw.close_vs_50d_ma, b.close_vs_50d_ma)

    setup = (
        w.breakout_52w * n_breakout
        + w.small_cap * n_smallcap
        + w.above_200d * n_above_200
    )
    catalyst = w.catalyst * n_catalyst + w.analyst_upgrades * n_upgrades
    momentum = (
        w.volume_trend * n_vol_trend
        + w.momentum_5d * n_momentum
        + w.above_50d * n_above_50
    )
    score = setup + catalyst + momentum

    reasons: list[str] = []
    if raw.close_vs_52w_high >= 0.92:
        pct = raw.close_vs_52w_high * 100
        if raw.tight_base:
            reasons.append(f"Fresh breakout from tight base ({pct:.0f}% of 52w high)")
        else:
            reasons.append(f"Near 52w high ({pct:.0f}% of high) but no recent base")

    if raw.market_cap_usd is not None and raw.market_cap_usd <= 2_000_000_000:
        reasons.append(f"Small cap (${raw.market_cap_usd/1e9:.2f}B)")

    above_200_pct = (raw.close_vs_200d_ma - 1.0) * 100.0
    if 2.0 <= above_200_pct <= 30.0:
        reasons.append(f"Above 200d MA in sweet spot (+{above_200_pct:.1f}%)")
    elif 30.0 < above_200_pct <= 50.0:
        reasons.append(f"Extended +{above_200_pct:.0f}% above 200d MA")
    elif above_200_pct > 50.0:
        reasons.append(f"WARN: over-extended +{above_200_pct:.0f}% above 200d MA")

    if raw.catalyst_score >= 0.5:
        reasons.append("Recent catalyst")
    if raw.analyst_upgrade_count_30d >= 2:
        reasons.append(f"{raw.analyst_upgrade_count_30d} analyst upgrades")
    if raw.volume_trend_5d >= 1.15:
        reasons.append(f"Volume expanding ({raw.volume_trend_5d:.2f}x baseline)")
    if raw.momentum_5d >= 0.05:
        reasons.append(f"5d momentum +{raw.momentum_5d*100:.1f}%")

    return round(score, 2), MoonshotLabels(
        setup=round(setup, 2),
        catalyst=round(catalyst, 2),
        momentum=round(momentum, 2),
        risk_level=moonshot_risk_level(score),
        confidence=moonshot_confidence(score, len(reasons)),
        reasons=reasons,
    )


def moonshot_risk_level(score: float) -> str:
    if score >= 70:
        return "Firing"
    if score >= 45:
        return "Loaded"
    if score >= 25:
        return "Setup"
    return "Watch"


def moonshot_confidence(score: float, reason_count: int) -> str:
    if score >= 60 and reason_count >= 4:
        return "High"
    if score >= 35 and reason_count >= 2:
        return "Medium"
    return "Low"
