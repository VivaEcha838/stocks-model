from __future__ import annotations

from squeeze_scanner.config import MOONSHOT_WEIGHTS
from squeeze_scanner.metrics import MoonshotFeatures
from squeeze_scanner.moonshot_scorer import (
    moonshot_confidence,
    moonshot_risk_level,
    score_moonshot,
)


def _zero_features() -> MoonshotFeatures:
    return MoonshotFeatures(
        close_vs_52w_high=0.50,
        market_cap_usd=50_000_000_000.0,
        close_vs_200d_ma=0.95,
        catalyst_score=0.0,
        analyst_upgrade_count_30d=0,
        volume_trend_5d=1.0,
        momentum_5d=0.0,
        close_vs_50d_ma=0.95,
    )


def _max_features() -> MoonshotFeatures:
    return MoonshotFeatures(
        close_vs_52w_high=1.05,
        market_cap_usd=200_000_000.0,
        close_vs_200d_ma=1.20,
        catalyst_score=1.0,
        analyst_upgrade_count_30d=8,
        volume_trend_5d=3.0,
        momentum_5d=0.25,
        close_vs_50d_ma=1.15,
        tight_base=True,
    )


def test_zero_features_zero_score():
    score, labels = score_moonshot(_zero_features())
    assert score == 0.0
    assert labels.setup == 0.0
    assert labels.catalyst == 0.0
    assert labels.momentum == 0.0
    assert labels.risk_level == "Watch"
    assert labels.confidence == "Low"
    assert labels.reasons == []


def test_max_features_max_score():
    score, labels = score_moonshot(_max_features())
    assert score == MOONSHOT_WEIGHTS.total() == 100.0
    assert labels.risk_level == "Firing"
    assert labels.confidence == "High"
    assert len(labels.reasons) >= 4


def test_only_setup_bucket():
    raw = _zero_features()
    raw.close_vs_52w_high = 1.0
    raw.market_cap_usd = 200_000_000.0
    raw.close_vs_200d_ma = 1.30
    raw.tight_base = True
    score, labels = score_moonshot(raw)
    assert labels.setup == MOONSHOT_WEIGHTS.breakout_52w + MOONSHOT_WEIGHTS.small_cap + MOONSHOT_WEIGHTS.above_200d
    assert labels.catalyst == 0.0
    assert labels.momentum == 0.0


def test_only_momentum_bucket():
    raw = _zero_features()
    raw.volume_trend_5d = 3.0
    raw.momentum_5d = 0.20
    raw.close_vs_50d_ma = 1.15
    score, labels = score_moonshot(raw)
    assert labels.setup == 0.0
    assert labels.catalyst == 0.0
    assert labels.momentum == MOONSHOT_WEIGHTS.volume_trend + MOONSHOT_WEIGHTS.momentum_5d + MOONSHOT_WEIGHTS.above_50d


def test_risk_thresholds():
    assert moonshot_risk_level(75) == "Firing"
    assert moonshot_risk_level(70) == "Firing"
    assert moonshot_risk_level(69.99) == "Loaded"
    assert moonshot_risk_level(45) == "Loaded"
    assert moonshot_risk_level(44.99) == "Setup"
    assert moonshot_risk_level(25) == "Setup"
    assert moonshot_risk_level(24.99) == "Watch"


def test_confidence_thresholds():
    assert moonshot_confidence(80, 5) == "High"
    assert moonshot_confidence(60, 4) == "High"
    assert moonshot_confidence(60, 3) == "Medium"
    assert moonshot_confidence(40, 2) == "Medium"
    assert moonshot_confidence(40, 1) == "Low"
    assert moonshot_confidence(10, 5) == "Low"


def test_extension_penalty_kicks_in():
    raw = _zero_features()
    raw.close_vs_200d_ma = 2.5
    score, labels = score_moonshot(raw)
    assert labels.setup == 0.0


def test_sweet_spot_gets_full_above_200d_credit():
    raw = _zero_features()
    raw.close_vs_200d_ma = 1.15
    score, labels = score_moonshot(raw)
    assert labels.setup == MOONSHOT_WEIGHTS.above_200d


def test_overextended_warning_appears_in_reasons():
    raw = _zero_features()
    raw.close_vs_200d_ma = 2.5
    score, labels = score_moonshot(raw)
    assert any("over-extended" in r.lower() for r in labels.reasons)


def test_sweet_spot_reason_appears_when_in_band():
    raw = _zero_features()
    raw.close_vs_200d_ma = 1.15
    score, labels = score_moonshot(raw)
    assert any("sweet spot" in r.lower() for r in labels.reasons)


def test_moderately_extended_reason_appears():
    raw = _zero_features()
    raw.close_vs_200d_ma = 1.40
    score, labels = score_moonshot(raw)
    assert any("Extended" in r and "over-extended" not in r.lower() for r in labels.reasons)


def test_volume_trend_reason_fires_at_lower_threshold():
    raw = _zero_features()
    raw.volume_trend_5d = 1.20
    score, labels = score_moonshot(raw)
    assert any("Volume expanding" in r for r in labels.reasons)


def test_breakout_penalized_without_tight_base():
    raw = _zero_features()
    raw.close_vs_52w_high = 1.0
    raw.tight_base = False
    score, labels = score_moonshot(raw)
    assert labels.setup < MOONSHOT_WEIGHTS.breakout_52w


def test_breakout_full_credit_with_tight_base():
    raw = _zero_features()
    raw.close_vs_52w_high = 1.0
    raw.tight_base = True
    score, labels = score_moonshot(raw)
    assert labels.setup == MOONSHOT_WEIGHTS.breakout_52w


def test_no_base_reason_when_at_high_but_no_base():
    raw = _zero_features()
    raw.close_vs_52w_high = 1.0
    raw.tight_base = False
    score, labels = score_moonshot(raw)
    assert any("no recent base" in r for r in labels.reasons)


def test_fresh_breakout_reason_when_at_high_with_base():
    raw = _zero_features()
    raw.close_vs_52w_high = 1.0
    raw.tight_base = True
    score, labels = score_moonshot(raw)
    assert any("Fresh breakout" in r for r in labels.reasons)
