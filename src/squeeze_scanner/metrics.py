from __future__ import annotations

from dataclasses import asdict, dataclass, field


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
    reasons: list[str] = field(default_factory=list)


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


@dataclass
class MoonshotFeatures:
    close_vs_52w_high: float
    market_cap_usd: float | None
    close_vs_200d_ma: float
    catalyst_score: float
    analyst_upgrade_count_30d: int
    volume_trend_5d: float
    momentum_5d: float
    close_vs_50d_ma: float
    tight_base: bool = False


@dataclass
class MoonshotLabels:
    setup: float
    catalyst: float
    momentum: float
    risk_level: str
    confidence: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class CrashFeatures:
    close_vs_50d_ma: float
    close_vs_200d_ma: float
    drawdown_from_52w: float
    distribution_day_count_20d: int
    analyst_downgrade_count_30d: int
    consecutive_down_days: int
    close_vs_20d_low: float
    gap_down_recent: bool


@dataclass
class CrashLabels:
    weakness: float
    distribution: float
    trigger: float
    risk_level: str
    confidence: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class MarketSnapshot:
    close: float
    volume: float
    avg_volume_30d: float
    high_20d: float
    high_52w: float
    low_20d: float
    sma_50d: float
    sma_200d: float
    vol_ratio: float
    breakout_pct: float
    drawdown_from_52w: float
    close_vs_50d_ma: float
    close_vs_200d_ma: float
    close_vs_20d_low: float
    momentum_5d: float
    volume_trend_5d: float
    consecutive_down_days: int
    distribution_day_count_20d: int
    gap_up_recent: bool
    gap_down_recent: bool
    tight_base: bool = False
    has_data_anomaly: bool = False
    max_single_day_move_pct: float = 0.0


@dataclass
class MultiTrackMetrics:
    ticker: str
    close: float
    volume: float
    avg_volume_30d: float
    high_20d: float
    high_52w: float
    sma_50d: float
    sma_200d: float
    market_cap_usd: float | None
    short_pct_float: float | None
    days_to_cover: float | None
    free_float_percent: float | None
    vol_ratio: float
    breakout_pct: float
    drawdown_from_52w: float
    catalyst_tag: str
    squeeze_score: float
    squeeze_labels: SqueezeLabels
    moonshot_score: float
    moonshot_labels: MoonshotLabels
    crash_score: float
    crash_labels: CrashLabels
    dominant: str
    action: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["squeeze_labels"] = asdict(self.squeeze_labels)
        d["moonshot_labels"] = asdict(self.moonshot_labels)
        d["crash_labels"] = asdict(self.crash_labels)
        return d
