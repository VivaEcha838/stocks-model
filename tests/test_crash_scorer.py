from __future__ import annotations

from squeeze_scanner.config import CRASH_WEIGHTS
from squeeze_scanner.crash_scorer import (
    crash_confidence,
    crash_risk_level,
    score_crash,
)
from squeeze_scanner.metrics import CrashFeatures


def _zero_features() -> CrashFeatures:
    return CrashFeatures(
        close_vs_50d_ma=1.05,
        close_vs_200d_ma=1.10,
        drawdown_from_52w=0.05,
        distribution_day_count_20d=0,
        analyst_downgrade_count_30d=0,
        consecutive_down_days=0,
        close_vs_20d_low=1.10,
        gap_down_recent=False,
    )


def _max_features() -> CrashFeatures:
    return CrashFeatures(
        close_vs_50d_ma=0.80,
        close_vs_200d_ma=0.75,
        drawdown_from_52w=0.50,
        distribution_day_count_20d=8,
        analyst_downgrade_count_30d=6,
        consecutive_down_days=8,
        close_vs_20d_low=0.99,
        gap_down_recent=True,
    )


def test_zero_features_zero_score():
    score, labels = score_crash(_zero_features())
    assert score == 0.0
    assert labels.weakness == 0.0
    assert labels.distribution == 0.0
    assert labels.trigger == 0.0
    assert labels.risk_level == "Stable"
    assert labels.confidence == "Low"
    assert labels.reasons == []


def test_max_features_max_score():
    score, labels = score_crash(_max_features())
    assert score == CRASH_WEIGHTS.total() == 100.0
    assert labels.risk_level == "Breaking"
    assert labels.confidence == "High"
    assert len(labels.reasons) >= 4


def test_only_weakness_bucket():
    raw = _zero_features()
    raw.close_vs_50d_ma = 0.80
    raw.close_vs_200d_ma = 0.75
    raw.drawdown_from_52w = 0.50
    score, labels = score_crash(raw)
    assert labels.weakness == CRASH_WEIGHTS.below_50d + CRASH_WEIGHTS.below_200d + CRASH_WEIGHTS.drawdown
    assert labels.distribution == 0.0
    assert labels.trigger == 0.0


def test_only_trigger_bucket():
    raw = _zero_features()
    raw.consecutive_down_days = 8
    raw.close_vs_20d_low = 0.99
    raw.gap_down_recent = True
    score, labels = score_crash(raw)
    assert labels.weakness == 0.0
    assert labels.distribution == 0.0
    assert labels.trigger == CRASH_WEIGHTS.consecutive_down + CRASH_WEIGHTS.breakdown_support + CRASH_WEIGHTS.gap_down


def test_risk_thresholds():
    assert crash_risk_level(75) == "Breaking"
    assert crash_risk_level(70) == "Breaking"
    assert crash_risk_level(69.99) == "Weakening"
    assert crash_risk_level(45) == "Weakening"
    assert crash_risk_level(44.99) == "Caution"
    assert crash_risk_level(25) == "Caution"
    assert crash_risk_level(24.99) == "Stable"


def test_confidence_thresholds():
    assert crash_confidence(80, 5) == "High"
    assert crash_confidence(60, 4) == "High"
    assert crash_confidence(60, 3) == "Medium"
    assert crash_confidence(40, 2) == "Medium"
    assert crash_confidence(40, 1) == "Low"
    assert crash_confidence(10, 5) == "Low"
