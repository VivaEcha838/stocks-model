from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val else default


API_KEY: str = _env("SQUEEZE_API_KEY", "")
BASE_URL: str = _env("SQUEEZE_BASE_URL", "https://api.polygon.io").rstrip("/")
MAX_WORKERS: int = int(_env("SQUEEZE_MAX_WORKERS", "4"))
OUTPUT_DIR: str = _env("SQUEEZE_OUTPUT_DIR", "out")
HTTP_TIMEOUT_SECONDS: int = 20


@dataclass(frozen=True)
class ScoringWeights:
    short_interest: float = 30.0
    float_tightness: float = 10.0
    days_to_cover: float = 20.0
    volume_spike: float = 20.0
    breakout: float = 15.0
    catalyst: float = 5.0

    def total(self) -> float:
        return (
            self.short_interest
            + self.float_tightness
            + self.days_to_cover
            + self.volume_spike
            + self.breakout
            + self.catalyst
        )


@dataclass(frozen=True)
class NormalizationBands:
    short_pct_float: tuple[float, float] = (10.0, 30.0)
    days_to_cover: tuple[float, float] = (2.0, 10.0)
    volume_ratio: tuple[float, float] = (1.0, 3.0)
    breakout_pct: tuple[float, float] = (0.0, 0.10)
    float_tightness_pct: tuple[float, float] = (40.0, 10.0)


@dataclass(frozen=True)
class MoonshotWeights:
    breakout_52w: float = 15.0
    small_cap: float = 10.0
    above_200d: float = 15.0
    catalyst: float = 15.0
    analyst_upgrades: float = 15.0
    volume_trend: float = 15.0
    momentum_5d: float = 10.0
    above_50d: float = 5.0

    def total(self) -> float:
        return (
            self.breakout_52w
            + self.small_cap
            + self.above_200d
            + self.catalyst
            + self.analyst_upgrades
            + self.volume_trend
            + self.momentum_5d
            + self.above_50d
        )


@dataclass(frozen=True)
class MoonshotBands:
    close_vs_52w_high: tuple[float, float] = (0.85, 1.00)
    market_cap_usd: tuple[float, float] = (10_000_000_000.0, 500_000_000.0)
    close_vs_200d_ma: tuple[float, float, float, float] = (0.95, 1.05, 1.30, 2.00)
    catalyst_score: tuple[float, float] = (0.0, 1.0)
    analyst_upgrade_count: tuple[float, float] = (0.0, 5.0)
    volume_trend_5d: tuple[float, float] = (1.0, 1.5)
    momentum_5d: tuple[float, float] = (0.0, 0.15)
    close_vs_50d_ma: tuple[float, float] = (0.95, 1.10)


@dataclass(frozen=True)
class CrashWeights:
    below_50d: float = 15.0
    below_200d: float = 15.0
    drawdown: float = 10.0
    distribution_days: float = 20.0
    analyst_downgrades: float = 10.0
    consecutive_down: float = 10.0
    breakdown_support: float = 10.0
    gap_down: float = 10.0

    def total(self) -> float:
        return (
            self.below_50d
            + self.below_200d
            + self.drawdown
            + self.distribution_days
            + self.analyst_downgrades
            + self.consecutive_down
            + self.breakdown_support
            + self.gap_down
        )


@dataclass(frozen=True)
class CrashBands:
    close_vs_50d_ma: tuple[float, float] = (1.00, 0.85)
    close_vs_200d_ma: tuple[float, float] = (1.00, 0.80)
    drawdown_from_52w: tuple[float, float] = (0.10, 0.40)
    distribution_day_count: tuple[float, float] = (1.0, 6.0)
    analyst_downgrade_count: tuple[float, float] = (0.0, 5.0)
    consecutive_down_days: tuple[float, float] = (2.0, 7.0)
    close_vs_20d_low: tuple[float, float] = (1.05, 1.00)


WEIGHTS = ScoringWeights()
BANDS = NormalizationBands()
MOONSHOT_WEIGHTS = MoonshotWeights()
MOONSHOT_BANDS = MoonshotBands()
CRASH_WEIGHTS = CrashWeights()
CRASH_BANDS = CrashBands()

assert WEIGHTS.total() == 100.0, "Squeeze weights must sum to 100"
assert MOONSHOT_WEIGHTS.total() == 100.0, "Moonshot weights must sum to 100"
assert CRASH_WEIGHTS.total() == 100.0, "Crash weights must sum to 100"
