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


WEIGHTS = ScoringWeights()
BANDS = NormalizationBands()

assert WEIGHTS.total() == 100.0, "Scoring weights must sum to 100"
