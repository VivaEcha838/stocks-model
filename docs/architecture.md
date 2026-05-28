# Architecture Notes

A short companion to [REQUIREMENTS.md](../REQUIREMENTS.md) — focuses on *why* the code is shaped the way it is, not *what* it does.

---

## Module diagram

```
                         ┌────────────┐
                         │   cli.py   │   argparse, table/CSV/JSON output
                         └──────┬─────┘
                                │ calls
                                ▼
                         ┌────────────┐
                         │ scanner.py │   per-ticker orchestration + threading
                         └──────┬─────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         ┌────────────┐  ┌────────────┐  ┌────────────┐
         │ client.py  │  │ scoring.py │  │ metrics.py │
         │ (HTTP I/O) │  │ (pure fn)  │  │ (datacls)  │
         └─────┬──────┘  └─────┬──────┘  └────────────┘
               │                │
               ▼                ▼
        ┌────────────┐    ┌────────────┐
        │ provider   │    │ config.py  │   weights, bands, env vars
        │ (Polygon)  │    └────────────┘
        └────────────┘
```

---

## Why these boundaries

**`scoring.py` is pure.** No HTTP, no env vars, no globals other than the immutable `WEIGHTS` and `BANDS` dataclasses. This is the part of the codebase the user will iterate on most — tweaking weights, adjusting bands, adding features. Keeping it pure means every change is testable in milliseconds without ever hitting the network.

**`client.py` is the only module that knows the provider exists.** If we swap Polygon.io for a different vendor (Tiingo, IEX Cloud, etc.), only `client.py` needs to change. The function signatures (`fetch_daily_bars(ticker, start, end) -> list[dict]`) are the contract.

**`scanner.py` owns failure modes.** It's the only place that catches exceptions and decides "skip this ticker, keep going." Both `client.py` and `scoring.py` raise; the orchestrator decides what's recoverable.

**`config.py` is a single source of truth.** Anything tunable — weights, bands, thread count, base URL — lives here. The assertion at the bottom (`assert WEIGHTS.total() == 100.0`) catches the most likely user mistake (re-weighting without keeping the sum at 100).

---

## Concurrency

`scan_universe` uses a `ThreadPoolExecutor` with `MAX_WORKERS` (default 4) to fan out per-ticker fetches in parallel. Each ticker scan is three sequential HTTP calls (bars → short interest → float), so we're I/O-bound — threads, not processes, are the right tool. Workers are bounded so we don't tip over the provider's rate limit.

---

## Why a band-based normalizer instead of z-scores

A z-score would be data-dependent: re-running the scan with a different universe would shift every score. Bands are absolute — *"30% short interest is full credit, period"* — so scores are comparable across runs and across universes. The cost is that bands need to be re-calibrated occasionally as market regimes change; that's a known trade-off and is called out in §8 of REQUIREMENTS.md as a backtesting follow-up.

---

## Testing strategy

- **Unit tests on `scoring.py`** — the high-leverage module. Boundary cases (all-zero, all-max, missing fields) plus mid-band sanity checks.
- **Manual / integration testing on `scanner.py` + `client.py`** — these need a real API key and real network, so they're not in CI by default. The `data/universe_sample.txt` file is the smoke test.
- **No mocks for the HTTP layer (yet).** When we add a backtest harness or a CI integration test, we'll add a recorded-fixtures pattern (`responses` library or saved JSON files) rather than hand-rolled mocks.
