"""Tests for market/backtest timestamp alignment."""

from datetime import datetime, timezone

import pytest

from src.timestamp_alignment import (
    TimestampAlignmentConfig,
    align_market_prices,
    standardise_timestamp,
    timestamp_alignment_report,
)


def test_standardise_timestamp_parses_space_and_t_separator():
    config = TimestampAlignmentConfig(interval_minutes=5)

    assert standardise_timestamp("2024-01-01 00:05:00", config) == datetime(2024, 1, 1, 0, 5)
    assert standardise_timestamp("2024-01-01T00:05:00", config) == datetime(2024, 1, 1, 0, 5)


def test_standardise_timestamp_converts_timezone_to_local_naive():
    config = TimestampAlignmentConfig(interval_minutes=5, timezone_name="Australia/Brisbane")

    assert standardise_timestamp("2023-12-31T14:05:00+00:00", config) == datetime(2024, 1, 1, 0, 5)
    assert standardise_timestamp(datetime(2023, 12, 31, 14, 5, tzinfo=timezone.utc), config) == datetime(2024, 1, 1, 0, 5)


def test_standardise_timestamp_rounds_to_interval():
    nearest = TimestampAlignmentConfig(interval_minutes=5, rounding="nearest")
    floor = TimestampAlignmentConfig(interval_minutes=5, rounding="floor")
    ceil = TimestampAlignmentConfig(interval_minutes=5, rounding="ceil")

    assert standardise_timestamp("2024-01-01 00:06:59", nearest) == datetime(2024, 1, 1, 0, 5)
    assert standardise_timestamp("2024-01-01 00:07:31", nearest) == datetime(2024, 1, 1, 0, 10)
    assert standardise_timestamp("2024-01-01 00:09:59", floor) == datetime(2024, 1, 1, 0, 5)
    assert standardise_timestamp("2024-01-01 00:05:01", ceil) == datetime(2024, 1, 1, 0, 10)


def test_timestamp_alignment_report_counts_matches_missing_and_duplicates():
    price_rows = [
        {"timestamp": "2024-01-01 00:05:00", "price_per_kwh": 0.10},
        {"timestamp": "2024-01-01T00:10:00", "price_per_kwh": 0.20},
        {"timestamp": "2024-01-01T00:10:00", "price_per_kwh": 0.21},
    ]
    backtest_rows = [
        {"timestamp": "2024-01-01T00:05:00", "price_per_kwh": 9.99},
        {"timestamp": "2024-01-01T00:15:00", "price_per_kwh": 9.99},
    ]

    report = timestamp_alignment_report(price_rows, backtest_rows)

    assert report["matched_rows"] == 1
    assert report["matched_percent"] == pytest.approx(50.0)
    assert report["missing_interval_count"] == 1
    assert report["duplicate_price_timestamps"] == {"2024-01-01T00:10:00": 2}
    assert report["unmatched_backtest_timestamps"] == ["2024-01-01T00:15:00"]


def test_align_market_prices_uses_market_price_not_embedded_backtest_price():
    price_rows = [
        {"timestamp": "2024-01-01 00:05:00", "price_per_kwh": 0.10},
    ]
    backtest_rows = [
        {"timestamp": "2024-01-01T00:05:00", "price_per_kwh": 9.99, "cashflow": 1.0},
    ]

    aligned, report = align_market_prices(price_rows, backtest_rows)

    assert report["matched_percent"] == pytest.approx(100.0)
    assert aligned[0]["regime_price"] == pytest.approx(0.10)
    assert aligned[0]["price_per_kwh"] == pytest.approx(9.99)
    assert aligned[0]["aligned_timestamp"] == datetime(2024, 1, 1, 0, 5)


def test_align_market_prices_fails_below_required_match_ratio():
    price_rows = [
        {"timestamp": "2024-01-01 00:05:00", "price_per_kwh": 0.10},
    ]
    backtest_rows = [
        {"timestamp": "2024-01-01T00:10:00", "price_per_kwh": 9.99},
    ]
    config = TimestampAlignmentConfig(min_match_ratio=1.0)

    with pytest.raises(ValueError, match="Timestamp alignment failed"):
        align_market_prices(price_rows, backtest_rows, config)


def test_invalid_alignment_config_raises_value_error():
    config = TimestampAlignmentConfig(interval_minutes=0)

    with pytest.raises(ValueError):
        timestamp_alignment_report([], [], config)
