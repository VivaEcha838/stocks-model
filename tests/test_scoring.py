"""Unit tests for the pure scoring layer — no network calls."""

from __future__ import annotations

from squeeze_scanner.config import WEIGHTS
from squeeze_scanner.metrics import RawFeatures
from squeeze_scanner.scoring import (
    clamp01,
    label_from_score,
    momentum_from_ignition,
    normalize_features,
    score_features,
)


def test_clamp_bounds():
    assert clamp01(-1) == 0.0
    assert clamp01(0) == 0.0
    assert clamp01(0.5) == 0.5
    assert clamp01(1.0) == 1.0
    assert clamp01(2.5) == 1.0


def test_zero_features_zero_score():
    raw = RawFeatures(
        short_pct_float=0.0,
        days_to_cover=0.0,
        volume_ratio=1.0,
        breakout_pct=0.0,
        float_tightness_pct=100.0,
        catalyst_score=0.0,
    )
    score, labels = score_features(raw)
    assert score == 0.0
    assert labels.fuel == 0.0
    assert labels.pressure == 0.0
    assert labels.ignition == 0.0
    assert labels.risk_level == "Low"
    assert labels.momentum == "Dormant"


def test_max_features_max_score():
    raw = RawFeatures(
        short_pct_float=40.0,        # > 30 cap
        days_to_cover=15.0,          # > 10 cap
        volume_ratio=5.0,            # > 3 cap
        breakout_pct=0.20,           # > 10% cap
        float_tightness_pct=5.0,     # < 10 cap (tighter is better)
        catalyst_score=1.0,
    )
    score, labels = score_features(raw)
    assert score == WEIGHTS.total() == 100.0
    assert labels.fuel == WEIGHTS.short_interest + WEIGHTS.float_tightness
    assert labels.pressure == WEIGHTS.days_to_cover
    assert labels.ignition == WEIGHTS.volume_spike + WEIGHTS.breakout + WEIGHTS.catalyst
    assert labels.risk_level == "Extreme"
    assert labels.momentum == "Active"


def test_buckets_split_correctly():
    """Only ignition features should populate the ignition bucket."""
    raw = RawFeatures(
        short_pct_float=0.0,
        days_to_cover=0.0,
        volume_ratio=3.0,            # full volume_spike
        breakout_pct=0.10,           # full breakout
        float_tightness_pct=100.0,
        catalyst_score=1.0,          # full catalyst
    )
    score, labels = score_features(raw)
    assert labels.fuel == 0.0
    assert labels.pressure == 0.0
    assert labels.ignition == WEIGHTS.volume_spike + WEIGHTS.breakout + WEIGHTS.catalyst
    assert score == labels.ignition


def test_label_thresholds():
    assert label_from_score(75) == "Extreme"
    assert label_from_score(70) == "Extreme"
    assert label_from_score(69.99) == "High"
    assert label_from_score(50) == "High"
    assert label_from_score(49.99) == "Moderate"
    assert label_from_score(30) == "Moderate"
    assert label_from_score(29.99) == "Low"
    assert label_from_score(0) == "Low"


def test_momentum_thresholds():
    assert momentum_from_ignition(40) == "Active"
    assert momentum_from_ignition(25) == "Active"
    assert momentum_from_ignition(24.99) == "Building"
    assert momentum_from_ignition(12) == "Building"
    assert momentum_from_ignition(11.99) == "Dormant"
    assert momentum_from_ignition(0) == "Dormant"


def test_missing_short_data_still_produces_score():
    """If short data is missing, that bucket goes to zero but the rest still counts."""
    raw = RawFeatures(
        short_pct_float=None,
        days_to_cover=None,
        volume_ratio=2.0,
        breakout_pct=0.05,
        float_tightness_pct=100.0,
        catalyst_score=0.0,
    )
    score, labels = score_features(raw)
    assert labels.fuel == 0.0
    assert labels.pressure == 0.0
    assert labels.ignition > 0.0
    assert score == labels.ignition


def test_normalization_midpoints():
    """A feature exactly at the midpoint of its band should normalize to ~0.5."""
    raw = RawFeatures(
        short_pct_float=20.0,        # midpoint of (10, 30)
        days_to_cover=6.0,           # midpoint of (2, 10)
        volume_ratio=2.0,            # midpoint of (1, 3)
        breakout_pct=0.05,           # midpoint of (0, 0.10)
        float_tightness_pct=25.0,    # midpoint of (40, 10) — descending band
        catalyst_score=0.5,
    )
    n = normalize_features(raw)
    for v in [n.short_interest, n.days_to_cover, n.volume_spike, n.breakout, n.float_tightness, n.catalyst]:
        assert abs(v - 0.5) < 1e-9
