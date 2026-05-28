from __future__ import annotations


SQUEEZE_ACTIONS = {
    "Extreme": "BUY SQUEEZE",
    "High": "LOAD",
    "Moderate": "MONITOR",
    "Low": "WATCH",
}

MOONSHOT_ACTIONS = {
    "Firing": "BUY MOMENTUM",
    "Loaded": "LOAD",
    "Setup": "MONITOR",
    "Watch": "WATCH",
}

CRASH_ACTIONS = {
    "Breaking": "EXIT / SHORT",
    "Weakening": "REDUCE",
    "Caution": "TIGHTEN STOPS",
    "Stable": "HOLD",
}

QUIET_THRESHOLD = 25.0
MIXED_SECONDARY_THRESHOLD = 40.0

WARNING_ACTION = "MONITOR (warning)"


def _has_warning(reasons: list[str] | None) -> bool:
    if not reasons:
        return False
    return any("WARN" in r for r in reasons)


def classify_dominant(
    squeeze_score: float,
    squeeze_risk: str,
    moonshot_score: float,
    moonshot_risk: str,
    crash_score: float,
    crash_risk: str,
    *,
    squeeze_reasons: list[str] | None = None,
    moonshot_reasons: list[str] | None = None,
    crash_reasons: list[str] | None = None,
) -> tuple[str, str]:
    scores = {
        "Squeeze": squeeze_score,
        "Moonshot": moonshot_score,
        "Crash": crash_score,
    }
    risks = {
        "Squeeze": squeeze_risk,
        "Moonshot": moonshot_risk,
        "Crash": crash_risk,
    }
    reasons_by_track = {
        "Squeeze": squeeze_reasons,
        "Moonshot": moonshot_reasons,
        "Crash": crash_reasons,
    }
    actions_by_track = {
        "Squeeze": SQUEEZE_ACTIONS,
        "Moonshot": MOONSHOT_ACTIONS,
        "Crash": CRASH_ACTIONS,
    }

    top_track = max(scores, key=lambda k: scores[k])
    top_score = scores[top_track]

    if top_score < QUIET_THRESHOLD:
        return "Quiet", "NO SETUP"

    other_scores = [v for k, v in scores.items() if k != top_track]
    if any(s >= MIXED_SECONDARY_THRESHOLD for s in other_scores):
        return "Mixed", "REVIEW MANUALLY"

    if _has_warning(reasons_by_track[top_track]):
        return top_track, WARNING_ACTION

    return top_track, actions_by_track[top_track].get(risks[top_track], "REVIEW")
