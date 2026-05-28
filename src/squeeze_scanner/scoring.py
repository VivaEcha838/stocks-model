from __future__ import annotations

from dataclasses import dataclass

from .config import BANDS, WEIGHTS
from .metrics import RawFeatures, SqueezeLabels


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _band_normalize(value: float, band: tuple[float, float]) -> float:
    zero_at, one_at = band
    if one_at == zero_at:
        return 0.0
    return clamp01((value - zero_at) / (one_at - zero_at))


def _peaked_normalize(value: float, band: tuple[float, float, float, float]) -> float:
    ramp_start, peak_low, peak_high, decay_end = band
    if value < ramp_start:
        return 0.0
    if value <= peak_low:
        if peak_low == ramp_start:
            return 1.0
        return clamp01((value - ramp_start) / (peak_low - ramp_start))
    if value <= peak_high:
        return 1.0
    if value < decay_end:
        if decay_end == peak_high:
            return 1.0
        return clamp01((decay_end - value) / (decay_end - peak_high))
    return 0.0


@dataclass
class NormalizedFeatures:
    short_interest: float
    days_to_cover: float
    volume_spike: float
    breakout: float
    float_tightness: float
    catalyst: float


def normalize_features(raw: RawFeatures) -> NormalizedFeatures:
    return NormalizedFeatures(
        short_interest=_band_normalize(raw.short_pct_float or 0.0, BANDS.short_pct_float),
        days_to_cover=_band_normalize(raw.days_to_cover or 0.0, BANDS.days_to_cover),
        volume_spike=_band_normalize(raw.volume_ratio, BANDS.volume_ratio),
        breakout=_band_normalize(raw.breakout_pct, BANDS.breakout_pct),
        float_tightness=_band_normalize(
            raw.float_tightness_pct if raw.float_tightness_pct is not None else 100.0,
            BANDS.float_tightness_pct,
        ),
        catalyst=clamp01(raw.catalyst_score),
    )


def score_features(raw: RawFeatures) -> tuple[float, SqueezeLabels]:
    n = normalize_features(raw)
    w = WEIGHTS

    fuel = w.short_interest * n.short_interest + w.float_tightness * n.float_tightness
    pressure = w.days_to_cover * n.days_to_cover
    ignition = (
        w.volume_spike * n.volume_spike
        + w.breakout * n.breakout
        + w.catalyst * n.catalyst
    )
    score = fuel + pressure + ignition

    reasons: list[str] = []
    if (raw.short_pct_float or 0) >= 15:
        reasons.append(f"Short interest {raw.short_pct_float:.1f}% of float")
    if (raw.days_to_cover or 0) >= 4:
        reasons.append(f"Days-to-cover {raw.days_to_cover:.1f}")
    if raw.volume_ratio >= 1.5:
        reasons.append(f"Volume {raw.volume_ratio:.2f}x average")
    if raw.breakout_pct >= 0.02:
        reasons.append(f"Breakout +{raw.breakout_pct*100:.1f}% above 20d high")
    if raw.catalyst_score >= 0.5:
        reasons.append("Active catalyst")

    return round(score, 2), SqueezeLabels(
        fuel=round(fuel, 2),
        pressure=round(pressure, 2),
        ignition=round(ignition, 2),
        risk_level=label_from_score(score),
        momentum=momentum_from_ignition(ignition),
        reasons=reasons,
    )


def label_from_score(score: float) -> str:
    if score >= 70:
        return "Extreme"
    if score >= 50:
        return "High"
    if score >= 30:
        return "Moderate"
    return "Low"


def momentum_from_ignition(ignition: float) -> str:
    if ignition >= 25:
        return "Active"
    if ignition >= 12:
        return "Building"
    return "Dormant"
