from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .config import OUTPUT_DIR
from .metrics import SqueezeMetrics
from .scanner import scan_universe


def _read_universe(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def _print_table(rows: list[SqueezeMetrics]) -> None:
    header = f"{'TICK':<6} {'SCORE':>6} {'FUEL':>6} {'PRES':>6} {'IGN':>6}  {'SI%':>6} {'DTC':>5} {'VOL×':>5}  {'RISK':<8} {'MOM':<8}  CATALYST"
    print(header)
    print("-" * len(header))
    for m in rows:
        print(
            f"{m.ticker:<6} "
            f"{m.score:>6.1f} "
            f"{m.labels.fuel:>6.1f} "
            f"{m.labels.pressure:>6.1f} "
            f"{m.labels.ignition:>6.1f}  "
            f"{(m.short_pct_float or 0):>6.1f} "
            f"{(m.days_to_cover or 0):>5.1f} "
            f"{m.vol_ratio:>5.2f}  "
            f"{m.labels.risk_level:<8} "
            f"{m.labels.momentum:<8}  "
            f"{m.catalyst_tag}"
        )


def _write_csv(rows: list[SqueezeMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "ticker", "score", "fuel", "pressure", "ignition",
            "risk_level", "momentum", "close", "volume", "avg_volume_30d",
            "high_20d", "breakout_pct", "vol_ratio",
            "short_pct_float", "days_to_cover",
            "free_float_shares", "free_float_percent",
            "short_interest_shares", "catalyst_tag",
        ])
        for m in rows:
            w.writerow([
                m.ticker, m.score, m.labels.fuel, m.labels.pressure, m.labels.ignition,
                m.labels.risk_level, m.labels.momentum, m.close, m.volume, m.avg_volume_30d,
                m.high_20d, m.breakout_pct, m.vol_ratio,
                m.short_pct_float, m.days_to_cover,
                m.free_float_shares, m.free_float_percent,
                m.short_interest_shares, m.catalyst_tag,
            ])


def _write_json(rows: list[SqueezeMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([m.to_dict() for m in rows], indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="squeeze", description="Short-squeeze candidate scanner")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--tickers", nargs="+", help="Tickers to scan, e.g. --tickers KSS IONQ GME")
    src.add_argument("--universe", type=Path, help="Path to a file with one ticker per line")
    p.add_argument("--start", help="Start date YYYY-MM-DD (default: ~200 days ago)")
    p.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    p.add_argument("--top", type=int, default=0, help="Only show the top N by score (0 = all)")
    p.add_argument("--csv", type=Path, help="Write results to a CSV file")
    p.add_argument("--json", dest="json_out", type=Path, help="Write results to a JSON file")
    args = p.parse_args(argv)

    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = _read_universe(args.universe)

    rows = scan_universe(tickers, start=args.start, end=args.end)
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
