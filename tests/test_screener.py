from __future__ import annotations

from squeeze_scanner.screener import (
    ScreenerConfig,
    SnapshotRow,
    parse_snapshot_row,
    screen_gainers,
    screen_gappers,
    screen_high_volume,
    screen_losers,
    screen_movers,
    screen_volatile,
)


def _row(ticker: str, **overrides) -> SnapshotRow:
    defaults = dict(
        ticker=ticker,
        close=50.0,
        volume=1_000_000.0,
        prev_close=49.0,
        prev_volume=900_000.0,
        todays_change_pct=2.04,
        open=49.5,
        high=51.0,
        low=49.0,
    )
    defaults.update(overrides)
    return SnapshotRow(**defaults)


def _sample_universe() -> list[SnapshotRow]:
    return [
        _row("AAA", todays_change_pct=15.0, volume=5_000_000),
        _row("BBB", todays_change_pct=-12.0, volume=3_000_000),
        _row("CCC", todays_change_pct=0.5, volume=200_000),
        _row("DDD", todays_change_pct=8.0, volume=1_500_000),
        _row("EEE", todays_change_pct=-3.0, volume=20_000_000, prev_volume=1_000_000),
        _row("FFF", todays_change_pct=4.0, close=0.50, volume=20_000_000),
        _row("GGG", todays_change_pct=5.0, close=15_000.0, volume=1_000_000),
        _row("HHH", todays_change_pct=1.0, open=55.0, prev_close=50.0, close=56.0),
        _row("III", todays_change_pct=-1.0, open=45.0, prev_close=50.0, close=46.0),
        _row("JJJ", todays_change_pct=0.1, high=60.0, low=50.0, close=55.0),
    ]


def test_parse_snapshot_row_well_formed():
    raw = {
        "ticker": "TEST",
        "day": {"c": 100.0, "v": 1_000_000, "o": 99.0, "h": 101.0, "l": 98.5},
        "prevDay": {"c": 98.0, "v": 800_000},
        "todaysChangePerc": 2.04,
    }
    row = parse_snapshot_row(raw)
    assert row is not None
    assert row.ticker == "TEST"
    assert row.close == 100.0
    assert row.todays_change_pct == 2.04


def test_parse_snapshot_row_drops_zero_price():
    raw = {
        "ticker": "ZERO",
        "day": {"c": 0.0, "v": 1_000_000},
        "prevDay": {"c": 0.0, "v": 800_000},
    }
    assert parse_snapshot_row(raw) is None


def test_parse_snapshot_row_drops_missing_ticker():
    raw = {
        "day": {"c": 100.0, "v": 1_000_000},
        "prevDay": {"c": 98.0, "v": 800_000},
    }
    assert parse_snapshot_row(raw) is None


def test_movers_ranks_by_absolute_change():
    out = screen_movers(_sample_universe(), max_results=3)
    assert out[0] == "AAA"
    assert out[1] == "BBB"
    assert "CCC" not in out


def test_gainers_only_positives_first():
    out = screen_gainers(_sample_universe(), max_results=3)
    assert out[0] == "AAA"
    assert out[1] == "DDD"


def test_losers_only_negatives_first():
    out = screen_losers(_sample_universe(), max_results=3)
    assert out[0] == "BBB"
    assert out[1] == "EEE"


def test_high_volume_ranks_by_volume_ratio():
    out = screen_high_volume(_sample_universe(), max_results=3)
    assert out[0] == "EEE"


def test_gappers_detects_gap_up_and_gap_down():
    out = screen_gappers(_sample_universe(), max_results=2)
    assert set(out[:2]) == {"HHH", "III"}


def test_volatile_ranks_by_intraday_range():
    out = screen_volatile(_sample_universe(), max_results=1)
    assert out[0] == "JJJ"


def test_min_price_excludes_penny_stocks():
    config = ScreenerConfig(min_price=1.0, min_volume=100_000)
    out = screen_movers(_sample_universe(), max_results=10, config=config)
    assert "FFF" not in out


def test_max_price_excludes_expensive_stocks():
    config = ScreenerConfig(min_price=1.0, max_price=1000.0, min_volume=100_000)
    out = screen_movers(_sample_universe(), max_results=10, config=config)
    assert "GGG" not in out


def test_min_volume_excludes_illiquid_stocks():
    config = ScreenerConfig(min_price=1.0, min_volume=500_000)
    out = screen_movers(_sample_universe(), max_results=10, config=config)
    assert "CCC" not in out


def test_max_results_caps_output():
    out = screen_movers(_sample_universe(), max_results=2)
    assert len(out) == 2


def test_min_dollar_volume_excludes_low_dollar_volume():
    rows = [
        _row("AAA", close=10.0, volume=1_000_000, todays_change_pct=5.0),
        _row("BBB", close=2.0, volume=100_000, todays_change_pct=10.0),
    ]
    config = ScreenerConfig(min_price=1.0, min_volume=0, min_dollar_volume=1_000_000)
    out = screen_movers(rows, max_results=10, config=config)
    assert "AAA" in out
    assert "BBB" not in out
