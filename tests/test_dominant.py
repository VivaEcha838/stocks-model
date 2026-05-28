from __future__ import annotations

from squeeze_scanner.dominant import classify_dominant


def test_quiet_when_all_below_threshold():
    track, action = classify_dominant(10, "Low", 12, "Watch", 8, "Stable")
    assert track == "Quiet"
    assert action == "NO SETUP"


def test_squeeze_dominant():
    track, action = classify_dominant(75, "Extreme", 20, "Watch", 15, "Stable")
    assert track == "Squeeze"
    assert action == "BUY SQUEEZE"


def test_moonshot_dominant():
    track, action = classify_dominant(15, "Low", 72, "Firing", 10, "Stable")
    assert track == "Moonshot"
    assert action == "BUY MOMENTUM"


def test_crash_dominant():
    track, action = classify_dominant(15, "Low", 20, "Watch", 80, "Breaking")
    assert track == "Crash"
    assert action == "EXIT / SHORT"


def test_mixed_when_two_high():
    track, action = classify_dominant(65, "High", 50, "Loaded", 12, "Stable")
    assert track == "Mixed"
    assert action == "REVIEW MANUALLY"


def test_mixed_when_three_high():
    track, action = classify_dominant(55, "High", 50, "Loaded", 45, "Weakening")
    assert track == "Mixed"
    assert action == "REVIEW MANUALLY"


def test_action_matches_risk_level():
    _, action = classify_dominant(55, "High", 20, "Watch", 10, "Stable")
    assert action == "LOAD"
    _, action = classify_dominant(35, "Moderate", 20, "Watch", 10, "Stable")
    assert action == "MONITOR"
    _, action = classify_dominant(20, "Low", 0, "Watch", 0, "Stable")
    assert action == "NO SETUP"


def test_warning_on_dominant_track_downgrades_action():
    track, action = classify_dominant(
        75, "Extreme", 20, "Watch", 15, "Stable",
        squeeze_reasons=["WARN: possible data anomaly"],
    )
    assert track == "Squeeze"
    assert action == "MONITOR (warning)"


def test_warning_on_non_dominant_track_does_not_downgrade():
    track, action = classify_dominant(
        75, "Extreme", 20, "Watch", 15, "Stable",
        moonshot_reasons=["WARN: over-extended"],
    )
    assert track == "Squeeze"
    assert action == "BUY SQUEEZE"


def test_warning_downgrades_crash_action_too():
    track, action = classify_dominant(
        15, "Low", 20, "Watch", 80, "Breaking",
        crash_reasons=["WARN: possible data anomaly"],
    )
    assert track == "Crash"
    assert action == "MONITOR (warning)"


def test_no_warning_means_normal_action():
    track, action = classify_dominant(
        75, "Extreme", 20, "Watch", 15, "Stable",
        squeeze_reasons=["Short interest 25%", "Days-to-cover 6.0"],
    )
    assert track == "Squeeze"
    assert action == "BUY SQUEEZE"


def test_overextended_warning_downgrades_moonshot():
    track, action = classify_dominant(
        15, "Low", 60, "Loaded", 10, "Stable",
        moonshot_reasons=["Near 52w high", "WARN: over-extended +120% above 200d MA"],
    )
    assert track == "Moonshot"
    assert action == "MONITOR (warning)"


def test_overextended_warning_at_setup_level_still_downgrades():
    track, action = classify_dominant(
        0.2, "Low", 42.8, "Setup", 5.9, "Stable",
        moonshot_reasons=["Small cap ($0.75B)", "WARN: over-extended +63% above 200d MA"],
    )
    assert track == "Moonshot"
    assert action == "MONITOR (warning)"
