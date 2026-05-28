# Software Requirements Specification — Squeeze Scanner

**Project:** Squeeze Scanner (under the GritFactor AI umbrella)
**Version:** 0.1.0
**Date:** 2026-04-23
**Author:** VivaEcha838

---

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements for **Squeeze Scanner**, a Python application that screens US equities for short-squeeze candidates. It is intended to feed a Software Requirements Document for a CS class deliverable as well as guide implementation.

### 1.2 Scope

Squeeze Scanner pulls short-interest, float, and price/volume data from a market-data provider (Polygon.io or a compatible API), evaluates each ticker against a multi-factor scoring model, and produces a ranked list of candidates with interpretable sub-scores. The system is delivered as a Python package with a command-line interface (CLI) and is designed so that a future web/mobile UI can sit on top of the same scoring core.

### 1.3 Definitions, Acronyms, Abbreviations

| Term | Meaning |
|---|---|
| **Short interest** | Total number of shares of a stock that have been sold short and not yet covered |
| **Float** | Shares of a stock available for public trading (excludes insider/restricted shares) |
| **Short % of float** | Short interest ÷ float, expressed as a percent |
| **Days to cover (DTC)** | Short interest ÷ average daily volume; rough estimate of how many trading days shorts would need to fully cover |
| **20d high** | Highest closing price over the previous 20 trading sessions |
| **Breakout** | Current price closing above (or near) the 20d high |
| **Catalyst** | A discrete event that re-rates the stock (earnings beat, partnership, FDA approval, viral social mention) |
| **Squeeze Score** | This system's 0–100 composite output |
| **SRD / SRS** | Software Requirements Document / Specification |

### 1.4 References

- User design notes (screenshots): "Best v1 product design" and "How You'd Build This in an App"
- Polygon.io REST docs (for API endpoint shapes): aggregates, short-interest, float

### 1.5 Overview

Section 2 frames the product. Section 3 enumerates functional and non-functional requirements. Section 4 describes the data model. Section 5 specifies the scoring algorithm in detail. Section 6 lists external interfaces. Section 7 defines verification criteria.

---

## 2. Overall Description

### 2.1 Product perspective

Squeeze Scanner is a standalone Python package. It is **not** a brokerage, a recommendation engine, or a real-time trading bot. It consumes a third-party market-data API, runs deterministic feature engineering and scoring, and emits a ranked CSV/JSON/table.

The system is structured so that:
- **Scoring** is a pure-function module with no I/O — fully unit-testable and easy to swap.
- **Data fetching** is isolated in a thin HTTP client — easy to mock, easy to replace if the provider changes.
- **Orchestration** ties them together and is the only layer that knows about concurrency, retries, and failure modes.

### 2.2 Product functions

1. Accept a list of tickers (CLI args or a universe file).
2. Fetch daily price/volume bars, short-interest reports, and float snapshots for each ticker.
3. Engineer features: 30-day average volume, 20-day high, volume ratio, breakout %, short % of float, days-to-cover, float tightness.
4. Normalize each feature into [0, 1] using calibration bands.
5. Apply weighted scoring to produce a 0–100 **Squeeze Score**, decomposed into **Fuel / Pressure / Ignition** sub-scores.
6. Tag each candidate with a **Risk Level** (Extreme / High / Moderate / Low) and a **Momentum Status** (Active / Building / Dormant).
7. Output a ranked table to stdout and optionally to CSV / JSON.

### 2.3 User characteristics

- Primary user: a retail/research-oriented analyst comfortable with the command line and reading a Python `requirements.txt`.
- Secondary user (future): a non-technical end user who consumes the same scoring through a hosted web dashboard.

### 2.4 Constraints

- **Data lag.** Short-interest data is reported biweekly with a multi-day delay — the system is therefore a *recipe-detector*, not a real-time intraday signal.
- **API rate limits.** The provider's free tier is rate-limited; concurrent requests must be bounded.
- **Single-machine.** v0.1 runs on a developer laptop. There is no scheduling, no shared database, no auth.

### 2.5 Assumptions and dependencies

- The provider exposes endpoints with the Polygon.io shape (`/v2/aggs/...`, `/stocks/vX/short-interest`, `/stocks/vX/float`).
- The user has Python 3.10 or newer installed.
- Network egress to the provider is allowed.

---

## 3. Specific Requirements

### 3.1 Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| **FR-1** | The system shall accept a list of tickers via a CLI flag (`--tickers`) **or** a path to a universe text file (`--universe`). Exactly one of the two shall be required. | Must |
| **FR-2** | The system shall fetch daily price/volume bars for each ticker, defaulting to a ~200-day window if no `--start`/`--end` is provided. | Must |
| **FR-3** | The system shall fetch the most recent short-interest report and float snapshot for each ticker. | Must |
| **FR-4** | The system shall skip (with a warning) any ticker that has fewer than 30 daily bars in the requested window. | Must |
| **FR-5** | The system shall compute the following derived features per ticker: 30-day average volume, 20-day rolling high, volume ratio (today ÷ 30d avg), breakout % vs 20d high, short % of float, days-to-cover. | Must |
| **FR-6** | The system shall normalize each feature into [0, 1] using the calibration bands defined in §5.2. | Must |
| **FR-7** | The system shall compute a 0–100 Squeeze Score using the weights defined in §5.3 and decompose it into Fuel, Pressure, and Ignition sub-scores. | Must |
| **FR-8** | The system shall classify each candidate's overall **Risk Level** as Extreme (≥70), High (≥50), Moderate (≥30), or Low (<30). | Must |
| **FR-9** | The system shall classify each candidate's **Momentum Status** based on the Ignition sub-score: Active (≥25), Building (≥12), Dormant (<12). | Must |
| **FR-10** | The system shall print a ranked, human-readable table to stdout, sorted by Squeeze Score descending. | Must |
| **FR-11** | The system shall optionally write results to CSV (`--csv`) and/or JSON (`--json`). When neither is given but results exist, it shall write a default CSV to `out/scan_latest.csv`. | Should |
| **FR-12** | The system shall optionally cap the printed/exported list to the top N entries via `--top N`. | Should |
| **FR-13** | The scoring layer shall expose a public Python API (`score_features(raw)`) so other components can score features without invoking the CLI. | Must |
| **FR-14** | The system shall accept an optional per-ticker catalyst signal (a 0–1 score and an opaque tag string) so news/event data from a future feed can be folded into the score. | Should |
| **FR-15** | The system shall not crash on a single failed ticker; failures shall be logged and the run shall continue. | Must |

### 3.2 Non-functional requirements

| ID | Requirement |
|---|---|
| **NFR-1 Performance** | Scanning a 25-ticker universe shall complete in under 60 seconds on a 100 Mbps connection (subject to provider rate limits). Concurrent fetches shall be bounded by `SQUEEZE_MAX_WORKERS` (default 4). |
| **NFR-2 Reliability** | A failed HTTP request for one ticker shall not abort the run. The system shall report a per-ticker skip message and continue. |
| **NFR-3 Configurability** | All weights and normalization bands shall live in a single config module (`config.py`). Changing a weight shall not require touching scoring logic. |
| **NFR-4 Testability** | The scoring module shall be a pure function with no I/O. ≥80% line coverage on `scoring.py` via `pytest`. |
| **NFR-5 Security** | The API key shall never be hardcoded; it shall be loaded from environment variable `SQUEEZE_API_KEY` or a local `.env` file. The `.env` file shall be in `.gitignore`. |
| **NFR-6 Portability** | The system shall run on Windows, macOS, and Linux with Python 3.10+. |
| **NFR-7 Maintainability** | The codebase shall follow PEP 8 and be organized into modules of <300 lines each. Public functions shall have type hints. |
| **NFR-8 Observability** | Skipped tickers shall be printed with the reason. The default output CSV shall record every input feature, not just the final score, so the score is reproducible from the row alone. |

---

## 4. Data Model

### 4.1 RawFeatures

| Field | Type | Description |
|---|---|---|
| `short_pct_float` | float\|None | Short interest as a percentage of float |
| `days_to_cover` | float\|None | Short interest ÷ 30-day average volume |
| `volume_ratio` | float | Today's volume ÷ 30-day average volume |
| `breakout_pct` | float | (close ÷ 20-day high) − 1 |
| `float_tightness_pct` | float | Free float as a percent of shares outstanding |
| `catalyst_score` | float | 0..1, externally supplied |

### 4.2 SqueezeLabels

| Field | Type | Description |
|---|---|---|
| `fuel` | float | Fuel sub-score (0..40) |
| `pressure` | float | Pressure sub-score (0..20) |
| `ignition` | float | Ignition sub-score (0..40) |
| `risk_level` | str | Extreme / High / Moderate / Low |
| `momentum` | str | Active / Building / Dormant |

### 4.3 SqueezeMetrics

End-to-end output for one ticker. Contains the raw inputs (close, volume, short interest, float), the derived features, the final score, and the labels. Designed to be flat enough to serialize directly to a CSV row.

---

## 5. Scoring Algorithm

### 5.1 Pipeline

```
   API responses
       ↓
   raw OHLCV / SI / float
       ↓
   feature engineering        ← scanner.py
       ↓
   RawFeatures
       ↓
   normalize_features         ← scoring.py (pure)
       ↓
   NormalizedFeatures (each in [0, 1])
       ↓
   weighted sum               ← scoring.py (pure)
       ↓
   (Squeeze Score, SqueezeLabels)
```

### 5.2 Normalization bands

Each band is a `(zero_at, one_at)` pair. Linear interpolation between the two; clamped to [0, 1] outside the range. If `zero_at > one_at`, smaller raw values normalize *higher* (used for float tightness).

| Feature | Band | Interpretation |
|---|---|---|
| Short % of float | (10%, 30%) | <10% gets 0, ≥30% gets full credit |
| Days to cover | (2, 10) | <2 gets 0, ≥10 gets full credit |
| Volume ratio | (1×, 3×) | At avg volume gets 0, ≥3× avg gets full credit |
| Breakout % | (0%, +10%) | At 20d high gets 0, +10% above gets full credit |
| Float tightness % | (40%, 10%) | Big float (≥40%) gets 0, very tight float (≤10%) gets full credit |
| Catalyst | (0, 1) | Already on a 0–1 scale |

### 5.3 Weights

| Component | Weight | Bucket |
|---|---|---|
| Short interest % of float | 30 | Fuel |
| Float tightness | 10 | Fuel |
| Days to cover | 20 | Pressure |
| Volume spike | 20 | Ignition |
| Breakout | 15 | Ignition |
| Catalyst | 5 | Ignition |
| **Total** | **100** | — |

`squeeze_score = Σ (weight_i × normalized_feature_i)`

### 5.4 Risk level thresholds

| Score | Label |
|---|---|
| ≥ 70 | Extreme |
| ≥ 50 | High |
| ≥ 30 | Moderate |
| < 30 | Low |

### 5.5 Momentum thresholds (Ignition sub-score)

| Ignition | Label |
|---|---|
| ≥ 25 | Active |
| ≥ 12 | Building |
| < 12 | Dormant |

### 5.6 Worked example

Suppose KSS today shows:
- short_pct_float = 27.5% → normalized = (27.5 − 10) / 20 = **0.875**
- days_to_cover = 8.2 → (8.2 − 2) / 8 = **0.775**
- volume_ratio = 2.65× → (2.65 − 1) / 2 = **0.825**
- breakout_pct = +4% → 0.04 / 0.10 = **0.40**
- float_tightness_pct = 32% → (40 − 32) / 30 = **0.267**
- catalyst_score = 0.6

Then:
- **Fuel** = 30 × 0.875 + 10 × 0.267 = 26.25 + 2.67 = **28.9**
- **Pressure** = 20 × 0.775 = **15.5**
- **Ignition** = 20 × 0.825 + 15 × 0.40 + 5 × 0.6 = 16.5 + 6.0 + 3.0 = **25.5**
- **Score** = 28.9 + 15.5 + 25.5 = **69.9** → Risk: High; Momentum: Active

---

## 6. External Interfaces

### 6.1 CLI

```
squeeze (--tickers TICKER [TICKER ...] | --universe FILE)
        [--start YYYY-MM-DD] [--end YYYY-MM-DD]
        [--top N]
        [--csv PATH] [--json PATH]
```

### 6.2 Python API

```python
from squeeze_scanner import scan_universe, scan_ticker, score_features

results = scan_universe(["KSS", "IONQ", "GME"])
for m in results[:5]:
    print(m.ticker, m.score, m.labels.risk_level)
```

### 6.3 Market-data provider

| Endpoint | Used for |
|---|---|
| `GET /v2/aggs/ticker/{T}/range/1/day/{from}/{to}` | Daily OHLCV bars |
| `GET /stocks/vX/short-interest?ticker={T}` | Most recent short-interest report |
| `GET /stocks/vX/float?ticker={T}` | Most recent float snapshot |

All requests carry `apiKey={SQUEEZE_API_KEY}` as a query parameter.

### 6.4 Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `SQUEEZE_API_KEY` | *(required)* | API key for the provider |
| `SQUEEZE_BASE_URL` | `https://api.polygon.io` | Provider base URL |
| `SQUEEZE_MAX_WORKERS` | `4` | Concurrent fetch threads |
| `SQUEEZE_OUTPUT_DIR` | `out` | Default output directory for CSV/JSON |

---

## 7. Verification & Acceptance

| Acceptance Criterion | How verified |
|---|---|
| All FR-* requirements are implemented | Manual CLI walkthrough using `data/universe_sample.txt` |
| Scoring math matches §5 | `pytest tests/test_scoring.py` — covers boundary cases (all-zero features → 0, all-max features → 100, individual buckets) |
| API failures don't crash the run | Manual test with an invalid `SQUEEZE_API_KEY` and with one bogus ticker in the universe |
| Output is reproducible from the CSV | Every input feature is present in the CSV row alongside the score |
| The codebase passes basic style review | `ruff check src/` (optional, dev-only) |

---

## 8. Future Work (out of scope for v0.1)

- **Catalyst feed.** Wire up a live news/earnings/SEC-filing source so `catalyst_score` is computed automatically instead of being a manual override.
- **Local cache** for short-interest and float data (they only update biweekly — no need to re-fetch every scan).
- **Backtest harness.** Replay historical scans and grade the top-N picks against the next 5/10/20-day price moves to calibrate weights and bands empirically rather than by intuition.
- **Options-flow signal.** Add a gamma-squeeze proxy (unusual call volume / open interest skew) as a 5–10 point Ignition feature.
- **Web dashboard.** FastAPI + React table that serves the same scoring core, with sortable columns and per-feature drill-down.
- **Universe presets.** Built-in S&P 500, Russell 2000, and a curated "high-SI" preset so the user does not have to maintain a `.txt` file.
