# Squeeze Scanner

A short-squeeze candidate scanner. Pulls short-interest, float, and price/volume data for a universe of US equities, scores each name on the **Fuel / Pressure / Ignition** framework, and ranks them.

> Built as part of the **GritFactor AI** project family.

---

## What it does

Given a list of tickers, it produces a ranked table that looks like:

```
TICK    SCORE   FUEL   PRES    IGN     SI%   DTC  VOL×    RISK     MOM       CATALYST
------------------------------------------------------------------------------------------
KSS      78.4   33.2   18.0   27.2    27.5   8.2  2.65    Extreme  Active    Earnings beat
IONQ     61.8   22.0   13.5   26.3    18.0   5.4  2.10    High     Active    Quantum partnership
GME      44.1   28.6   15.2    0.3    24.0   7.6  1.04    Moderate Dormant
```

The score is a 0–100 composite that decomposes into three buckets so you can tell *why* a name is ranked where it is.

---

## The model in one paragraph

A short squeeze needs three things in the same window: a lot of shorts trapped (**Fuel**), enough volume math that they can't quietly cover (**Pressure**), and a real spark — volume spike, breakout, or catalyst — that forces the unwind (**Ignition**). This scanner measures each.

| Bucket | Weight | Sub-features |
|---|---|---|
| **Fuel** | 40 | Short interest % of float (30) + float tightness (10) |
| **Pressure** | 20 | Days-to-cover (short interest ÷ 30d avg vol) |
| **Ignition** | 40 | Volume spike vs 30d avg (20) + breakout vs 20d high (15) + catalyst (5) |

Each raw feature is normalized into [0, 1] using a calibration band, then multiplied by its weight. See [REQUIREMENTS.md](REQUIREMENTS.md) for the full spec.

---

## Quick start

### 1. Install

```bash
git clone https://github.com/<your-user>/squeeze-scanner.git
cd squeeze-scanner
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                   # installs the `squeeze` CLI
```

### 2. Configure

```bash
cp .env.example .env
# edit .env and set SQUEEZE_API_KEY=<your Polygon.io (or compatible) key>
```

The scanner expects a Polygon.io-shaped API. The base URL is configurable via `SQUEEZE_BASE_URL`.

### 3. Run

```bash
# Score a small list inline:
squeeze --tickers KSS IONQ GME BYND --top 5

# Or use the sample universe file:
squeeze --universe data/universe_sample.txt --csv out/today.csv

# Use a custom date window:
squeeze --tickers KSS --start 2025-10-01 --end 2026-04-22
```

Module form also works: `python -m squeeze_scanner --tickers KSS IONQ`.

### 4. Test

```bash
pytest -q
```

The scoring layer is fully unit-tested with no network calls.

---

## Project layout

```
.
├── src/squeeze_scanner/
│   ├── config.py      # weights, normalization bands, env vars
│   ├── client.py      # HTTP layer for the market-data provider
│   ├── metrics.py     # dataclasses (RawFeatures, SqueezeMetrics, Labels)
│   ├── scoring.py     # pure-function scorer — no I/O
│   ├── scanner.py     # orchestrator — fetch → score → rank
│   ├── cli.py         # argparse CLI, table/CSV/JSON output
│   └── __main__.py    # `python -m squeeze_scanner`
├── tests/             # pytest unit tests for the scoring layer
├── data/              # sample universe files
├── docs/              # design notes, architecture diagrams
├── REQUIREMENTS.md    # software requirements doc (SRD)
└── pyproject.toml
```

---

## Roadmap

- [ ] Real catalyst feed (news/earnings/SEC filings) instead of manual `catalyst_score`
- [ ] Local cache for short-interest / float (they only update biweekly anyway)
- [ ] Universe management — built-in S&P 500 / Russell 2000 / "high-SI" preset lists
- [ ] Backtest harness — replay historical scans and grade them against actual price moves
- [ ] Options-flow signal as a bonus Ignition feature (gamma squeeze)
- [ ] Web dashboard (FastAPI + small React table) on top of the CSV output

---

## Disclaimer

This is a research tool, not investment advice. Short-interest data is reported on a delay (typically biweekly) — the scanner is a *recipe-detector*, not a real-time guarantee. Trade at your own risk.
