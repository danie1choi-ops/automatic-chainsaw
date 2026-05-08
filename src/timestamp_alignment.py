"""Timestamp normalisation and market/backtest interval alignment."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class TimestampAlignmentConfig:
    """Configuration for interval timestamp alignment."""

    interval_minutes: int = 5
    timezone_name: str = "Australia/Brisbane"
    rounding: str = "nearest"
    min_match_ratio: float = 1.0
    sample_size: int = 10

    def validate(self) -> None:
        if self.interval_minutes <= 0:
            raise ValueError("interval_minutes must be greater than zero")
        if self.rounding not in {"nearest", "floor", "ceil"}:
            raise ValueError("rounding must be one of: nearest, floor, ceil")
        if not 0 <= self.min_match_ratio <= 1:
            raise ValueError("min_match_ratio must be between 0 and 1")
        if self.sample_size < 0:
            raise ValueError("sample_size cannot be negative")


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse common timestamp values into datetime objects."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def standardise_timestamp(
    value: Any,
    config: Optional[TimestampAlignmentConfig] = None,
) -> Optional[datetime]:
    """Parse, timezone-normalise, round, and return a naive local timestamp."""
    cfg = config or TimestampAlignmentConfig()
    cfg.validate()
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return None

    local_tz = ZoneInfo(cfg.timezone_name)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=local_tz)
    else:
        timestamp = timestamp.astimezone(local_tz)

    rounded = round_timestamp(timestamp, cfg.interval_minutes, cfg.rounding)
    return rounded.replace(tzinfo=None)


def format_timestamp(value: Optional[datetime]) -> Optional[str]:
    """Format aligned timestamps consistently for CSV diagnostics."""
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def timestamp_alignment_report(
    price_rows: Sequence[Dict[str, Any]],
    backtest_rows: Sequence[Dict[str, Any]],
    config: Optional[TimestampAlignmentConfig] = None,
) -> Dict[str, Any]:
    """Return diagnostics for market price to backtest timestamp alignment."""
    cfg = config or TimestampAlignmentConfig()
    cfg.validate()

    price_timestamps = [
        standardise_timestamp(row.get("timestamp"), cfg)
        for row in price_rows
    ]
    backtest_timestamps = [
        standardise_timestamp(row.get("timestamp"), cfg)
        for row in backtest_rows
    ]

    price_counts = Counter(ts for ts in price_timestamps if ts is not None)
    backtest_counts = Counter(ts for ts in backtest_timestamps if ts is not None)
    price_set = set(price_counts)
    backtest_set = set(backtest_counts)

    matched_timestamps = backtest_set & price_set
    matched_rows = sum(1 for ts in backtest_timestamps if ts in price_set)
    total_backtest_rows = len(backtest_rows)
    match_ratio = matched_rows / total_backtest_rows if total_backtest_rows else 0.0

    unmatched_backtest = [
        ts for ts in backtest_timestamps
        if ts is not None and ts not in price_set
    ]
    missing_market_intervals = sorted(backtest_set - price_set)
    unused_market_intervals = sorted(price_set - backtest_set)
    duplicate_price_timestamps = {
        format_timestamp(ts): count
        for ts, count in sorted(price_counts.items())
        if count > 1
    }
    duplicate_backtest_timestamps = {
        format_timestamp(ts): count
        for ts, count in sorted(backtest_counts.items())
        if count > 1
    }

    return {
        "total_price_rows": len(price_rows),
        "total_backtest_rows": total_backtest_rows,
        "matched_rows": matched_rows,
        "matched_unique_timestamps": len(matched_timestamps),
        "match_ratio": match_ratio,
        "matched_percent": match_ratio * 100.0,
        "missing_interval_count": len(missing_market_intervals),
        "unused_market_interval_count": len(unused_market_intervals),
        "duplicate_price_timestamps": duplicate_price_timestamps,
        "duplicate_backtest_timestamps": duplicate_backtest_timestamps,
        "unmatched_backtest_timestamps": [
            format_timestamp(ts)
            for ts in unmatched_backtest[:cfg.sample_size]
        ],
        "missing_market_intervals": [
            format_timestamp(ts)
            for ts in missing_market_intervals[:cfg.sample_size]
        ],
        "unused_market_intervals": [
            format_timestamp(ts)
            for ts in unused_market_intervals[:cfg.sample_size]
        ],
        "price_start": format_timestamp(min(price_set)) if price_set else None,
        "price_end": format_timestamp(max(price_set)) if price_set else None,
        "backtest_start": format_timestamp(min(backtest_set)) if backtest_set else None,
        "backtest_end": format_timestamp(max(backtest_set)) if backtest_set else None,
        "config": {
            "interval_minutes": cfg.interval_minutes,
            "timezone_name": cfg.timezone_name,
            "rounding": cfg.rounding,
            "min_match_ratio": cfg.min_match_ratio,
        },
    }


def align_market_prices(
    price_rows: Sequence[Dict[str, Any]],
    backtest_rows: Sequence[Dict[str, Any]],
    config: Optional[TimestampAlignmentConfig] = None,
    price_field: str = "price_per_kwh",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Attach aligned market prices to backtest rows.

    Raises ValueError when the matched interval percentage is below the
    configured minimum. This prevents regime attribution from silently using
    embedded backtest prices.
    """
    cfg = config or TimestampAlignmentConfig()
    cfg.validate()
    report = timestamp_alignment_report(price_rows, backtest_rows, cfg)

    price_by_timestamp: Dict[datetime, Dict[str, Any]] = {}
    for row in price_rows:
        timestamp = standardise_timestamp(row.get("timestamp"), cfg)
        if timestamp is None:
            continue
        if timestamp not in price_by_timestamp:
            price_by_timestamp[timestamp] = row

    aligned_rows = []
    for row in backtest_rows:
        aligned_timestamp = standardise_timestamp(row.get("timestamp"), cfg)
        if aligned_timestamp is None or aligned_timestamp not in price_by_timestamp:
            continue
        price_row = price_by_timestamp[aligned_timestamp]
        aligned = dict(row)
        aligned["aligned_timestamp"] = aligned_timestamp
        aligned["regime_price"] = float(price_row[price_field])
        aligned["market_price_timestamp"] = aligned_timestamp
        aligned_rows.append(aligned)

    if report["match_ratio"] < cfg.min_match_ratio:
        raise ValueError(
            "Timestamp alignment failed: "
            f"{report['matched_percent']:.2f}% matched, "
            f"minimum required is {cfg.min_match_ratio * 100.0:.2f}%"
        )

    return aligned_rows, report


def round_timestamp(timestamp: datetime, interval_minutes: int, mode: str) -> datetime:
    interval_seconds = interval_minutes * 60
    day_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (timestamp - day_start).total_seconds()

    if mode == "floor":
        rounded_seconds = int(elapsed // interval_seconds) * interval_seconds
    elif mode == "ceil":
        rounded_seconds = int((elapsed + interval_seconds - 1) // interval_seconds) * interval_seconds
    else:
        rounded_seconds = int((elapsed + interval_seconds / 2) // interval_seconds) * interval_seconds

    return day_start + timedelta(seconds=rounded_seconds)
