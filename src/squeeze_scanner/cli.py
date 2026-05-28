from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .config import OUTPUT_DIR
from .metrics import MultiTrackMetrics
from .scanner import scan_universe
from .screener import SCREENERS, ScreenerConfig, load_market_snapshot


def _read_universe(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def _print_table(rows: list[MultiTrackMetrics]) -> None:
    header = (
        f"{'TICK':<6} "
        f"{'SQ':>6} {'MS':>6} {'CR':>6}  "
        f"{'DOMINANT':<10} "
        f"{'ACTION':<16}  "
        f"WHY"
    )
    print(header)
    print("-" * len(header))
    for m in rows:
        if m.dominant == "Squeeze":
            reasons = m.squeeze_labels.reasons
        elif m.dominant == "Moonshot":
            reasons = m.moonshot_labels.reasons
        elif m.dominant == "Crash":
            reasons = m.crash_labels.reasons
        else:
            reasons = []
        why = "; ".join(reasons[:2]) if reasons else ""
        print(
            f"{m.ticker:<6} "
            f"{m.squeeze_score:>6.1f} "
            f"{m.moonshot_score:>6.1f} "
            f"{m.crash_score:>6.1f}  "
            f"{m.dominant:<10} "
            f"{m.action:<16}  "
            f"{why}"
        )


def _write_csv(rows: list[MultiTrackMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "ticker", "dominant", "action",
            "squeeze_score", "squeeze_fuel", "squeeze_pressure", "squeeze_ignition",
            "squeeze_risk", "squeeze_momentum", "squeeze_reasons",
            "moonshot_score", "moonshot_setup", "moonshot_catalyst", "moonshot_momentum",
            "moonshot_risk", "moonshot_confidence", "moonshot_reasons",
            "crash_score", "crash_weakness", "crash_distribution", "crash_trigger",
            "crash_risk", "crash_confidence", "crash_reasons",
            "close", "volume", "avg_volume_30d",
            "high_20d", "high_52w", "sma_50d", "sma_200d",
            "vol_ratio", "breakout_pct", "drawdown_from_52w",
            "market_cap_usd", "short_pct_float", "days_to_cover",
            "free_float_percent", "catalyst_tag",
        ])
        for m in rows:
            w.writerow([
                m.ticker, m.dominant, m.action,
                m.squeeze_score, m.squeeze_labels.fuel, m.squeeze_labels.pressure, m.squeeze_labels.ignition,
                m.squeeze_labels.risk_level, m.squeeze_labels.momentum, "; ".join(m.squeeze_labels.reasons),
                m.moonshot_score, m.moonshot_labels.setup, m.moonshot_labels.catalyst, m.moonshot_labels.momentum,
                m.moonshot_labels.risk_level, m.moonshot_labels.confidence, "; ".join(m.moonshot_labels.reasons),
                m.crash_score, m.crash_labels.weakness, m.crash_labels.distribution, m.crash_labels.trigger,
                m.crash_labels.risk_level, m.crash_labels.confidence, "; ".join(m.crash_labels.reasons),
                m.close, m.volume, m.avg_volume_30d,
                m.high_20d, m.high_52w, m.sma_50d, m.sma_200d,
                m.vol_ratio, m.breakout_pct, m.drawdown_from_52w,
                m.market_cap_usd, m.short_pct_float, m.days_to_cover,
                m.free_float_percent, m.catalyst_tag,
            ])


def _write_json(rows: list[MultiTrackMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([m.to_dict() for m in rows], indent=2, default=str))


def _filter_rows(rows: list[MultiTrackMetrics], track: str | None) -> list[MultiTrackMetrics]:
    if not track:
        return rows
    track = track.capitalize()
    return [m for m in rows if m.dominant == track]


def _filter_by_market_cap(rows: list[MultiTrackMetrics], min_cap: float) -> list[MultiTrackMetrics]:
    if min_cap <= 0:
        return rows
    return [r for r in rows if (r.market_cap_usd or 0) >= min_cap]


def _resolve_universe(args: argparse.Namespace) -> list[str]:
    if args.screen:
        config = ScreenerConfig(
            min_price=args.min_price,
            max_price=args.max_price,
            min_volume=args.min_volume,
            min_dollar_volume=args.min_dollar_volume,
        )
        print(f"[screen] Loading market snapshot from Polygon...", file=sys.stderr)
        snapshot = load_market_snapshot()
        print(f"[screen] {len(snapshot)} active tickers received", file=sys.stderr)
        tickers = SCREENERS[args.screen](snapshot, args.screen_size, config)
        print(f"[screen] '{args.screen}' filter → {len(tickers)} candidates", file=sys.stderr)
        return tickers
    if args.tickers:
        return [t.upper() for t in args.tickers]
    if args.universe:
        return _read_universe(args.universe)
    raise SystemExit("Must specify one of --tickers, --universe, or --screen")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="squeeze", description="Multi-track short-squeeze / moonshot / crash scanner")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--tickers", nargs="+", help="Tickers to scan, e.g. --tickers KSS IONQ GME")
    src.add_argument("--universe", type=Path, help="Path to a file with one ticker per line")
    src.add_argument("--screen", choices=list(SCREENERS.keys()), help="Pre-screen the entire US market with this filter")
    p.add_argument("--screen-size", type=int, default=100, help="Candidates to pull from --screen (default 100)")
    p.add_argument("--min-price", type=float, default=1.0, help="Min stock price for --screen filter")
    p.add_argument("--max-price", type=float, default=10000.0, help="Max stock price for --screen filter")
    p.add_argument("--min-volume", type=float, default=100_000.0, help="Min daily share volume for --screen filter")
    p.add_argument("--min-dollar-volume", type=float, default=1_000_000.0, help="Min daily dollar volume (price * volume) for --screen filter, default $1M")
    p.add_argument("--min-market-cap", type=float, default=200_000_000.0, help="Drop results with market cap below this (default $200M). Set 0 to disable.")
    p.add_argument("--start", help="Start date YYYY-MM-DD (default: ~400 days ago)")
    p.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    p.add_argument("--top", type=int, default=0, help="Only show the top N (0 = all)")
    p.add_argument("--track", choices=["squeeze", "moonshot", "crash", "mixed", "quiet"], help="Filter output to this dominant track")
    p.add_argument("--csv", type=Path, help="Write results to a CSV file")
    p.add_argument("--json", dest="json_out", type=Path, help="Write results to a JSON file")
    args = p.parse_args(argv)

    tickers = _resolve_universe(args)
    if not tickers:
        print("No tickers to scan.", file=sys.stderr)
        return 1

    print(f"[scan] Deep-scoring {len(tickers)} tickers...", file=sys.stderr)
    rows = scan_universe(tickers, start=args.start, end=args.end)
    if args.min_market_cap > 0:
        before = len(rows)
        rows = _filter_by_market_cap(rows, args.min_market_cap)
        dropped = before - len(rows)
        if dropped:
            print(f"[filter] dropped {dropped} rows below ${args.min_market_cap/1e6:.0f}M market cap", file=sys.stderr)
    rows = _filter_rows(rows, args.track)
    if args.top:
        rows = rows[: args.top]

    _print_table(rows)

    if args.csv:
        _write_csv(rows, args.csv)
        print(f"\nWrote CSV: {args.csv}")
    if args.json_out:
        _write_json(rows, args.json_out)
        print(f"Wrote JSON: {args.json_out}")

    if not args.csv and not args.json_out and rows:
        default_csv = Path(OUTPUT_DIR) / "scan_latest.csv"
        _write_csv(rows, default_csv)
        print(f"\nWrote CSV: {default_csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
