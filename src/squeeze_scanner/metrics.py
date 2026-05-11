from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class RawFeatures:
    short_pct_float: float | None
    days_to_cover: float | None
    volume_ratio: float
    breakout_pct: float
    float_tightness_pct: float
    catalyst_score: float = 0.0


@dataclass
class SqueezeLabels:
    fuel: float
    pressure: float
    ignition: float
    risk_level: str
    momentum: str


@dataclass
class SqueezeMetrics:
    ticker: str
    close: float
    volume: float
    avg_volume_30d: float
    high_20d: float
    short_interest_shares: float
    free_float_shares: float | None
    free_float_percent: float | None
    short_pct_float: float | None
    days_to_cover: float | None
    vol_ratio: float
    breakout_pct: float
    catalyst_tag: str
    score: float
    labels: SqueezeLabels

    def to_dict(self) -> dict:
        d = asdict(self)
        d["labels"] = asdict(self.labels)
        return d
