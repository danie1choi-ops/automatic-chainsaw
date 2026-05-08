"""Historical price regime analysis for NEM-style price series.

This module is purely analytical. It classifies market price conditions and
summarises regime frequency, duration, price levels, and transitions. It does
not contain battery dispatch or trading logic.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Sequence, Tuple


NORMAL = "normal"
VOLATILE = "volatile"
NEGATIVE_PRICING = "negative_pricing"
PRICE_SPIKE = "price_spike"
SUSTAINED_HIGH_PRICE_EVENT = "sustained_high_price_event"

REGIMES = (
    NORMAL,
    VOLATILE,
    NEGATIVE_PRICING,
    PRICE_SPIKE,
    SUSTAINED_HIGH_PRICE_EVENT,
)


@dataclass(frozen=True)
class RegimeAnalysisConfig:
    """Configurable thresholds for price regime classification.

    Thresholds are unit-agnostic. If prices are supplied in $/MWh, threshold
    values should also be $/MWh. If prices are supplied in $/kWh, threshold
    values should also be $/kWh.
    """

    negative_price_threshold: float = 0.0
    high_price_percentile: float = 0.90
    spike_price_percentile: float = 0.98
    volatility_percentile: float = 0.90
    rolling_window_intervals: int = 12
    sustained_high_intervals: int = 6
    interval_hours: float = 5.0 / 60.0
    high_price_threshold: Optional[float] = None
    spike_price_threshold: Optional[float] = None
    volatility_threshold: Optional[float] = None

    def validate(self) -> None:
        """Validate threshold configuration."""
        for name, value in (
            ("high_price_percentile", self.high_price_percentile),
            ("spike_price_percentile", self.spike_price_percentile),
            ("volatility_percentile", self.volatility_percentile),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.rolling_window_intervals <= 0:
            raise ValueError("rolling_window_intervals must be greater than zero")
        if self.sustained_high_intervals <= 0:
            raise ValueError("sustained_high_intervals must be greater than zero")
        if self.interval_hours <= 0:
            raise ValueError("interval_hours must be greater than zero")


@dataclass(frozen=True)
class RegimeInterval:
    """Classified price interval."""

    index: int
    timestamp: Optional[datetime]
    price: float
    rolling_volatility: Optional[float]
    consecutive_high_intervals: int
    regime: str


def classify_interval(
    price: float,
    config: Optional[RegimeAnalysisConfig] = None,
    high_price_threshold: Optional[float] = None,
    spike_price_threshold: Optional[float] = None,
    rolling_volatility: Optional[float] = None,
    volatility_threshold: Optional[float] = None,
    consecutive_high_intervals: int = 0,
) -> str:
    """Classify a single interval from price and precomputed context.

    Priority order is negative pricing, price spike, sustained high-price event,
    volatile, then normal.
    """
    config = config or RegimeAnalysisConfig()
    config.validate()

    high_threshold = _first_not_none(high_price_threshold, config.high_price_threshold)
    spike_threshold = _first_not_none(spike_price_threshold, config.spike_price_threshold)
    vol_threshold = _first_not_none(volatility_threshold, config.volatility_threshold)

    if price < config.negative_price_threshold:
        return NEGATIVE_PRICING
    if spike_threshold is not None and price >= spike_threshold:
        return PRICE_SPIKE
    if (
        high_threshold is not None
        and price >= high_threshold
        and consecutive_high_intervals >= config.sustained_high_intervals
    ):
        return SUSTAINED_HIGH_PRICE_EVENT
    if (
        rolling_volatility is not None
        and vol_threshold is not None
        and rolling_volatility > vol_threshold
    ):
        return VOLATILE
    return NORMAL


def classify_day(
    records: Sequence[Any],
    config: Optional[RegimeAnalysisConfig] = None,
    price_field: Optional[str] = None,
    timestamp_field: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify one day's intervals and return day-level regime metrics."""
    intervals = _classify_records(records, config, price_field, timestamp_field)
    if not intervals:
        raise ValueError("records must contain at least one price")

    frequencies = _frequency_by_regime(intervals)
    avg_price_by_regime = _average_price_by_regime(intervals)
    dominant_regime = max(frequencies, key=lambda regime: frequencies[regime]["count"])
    day_value = _day_from_intervals(intervals)

    return {
        "date": day_value,
        "dominant_regime": dominant_regime,
        "interval_count": len(intervals),
        "frequency": frequencies,
        "average_price_by_regime": avg_price_by_regime,
        "intervals": intervals,
    }


def summarise_regimes(
    records: Sequence[Any],
    config: Optional[RegimeAnalysisConfig] = None,
    price_field: Optional[str] = None,
    timestamp_field: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify a price series and summarise regime statistics."""
    cfg = config or RegimeAnalysisConfig()
    intervals = _classify_records(records, cfg, price_field, timestamp_field)
    if not intervals:
        raise ValueError("records must contain at least one price")

    return {
        "interval_count": len(intervals),
        "frequency": _frequency_by_regime(intervals),
        "average_duration_hours": _average_duration_by_regime(intervals, cfg.interval_hours),
        "average_price_by_regime": _average_price_by_regime(intervals),
        "transitions": _transition_statistics(intervals),
        "classified_intervals": intervals,
        "thresholds": _resolved_thresholds([item.price for item in intervals], cfg),
    }


def _classify_records(
    records: Sequence[Any],
    config: Optional[RegimeAnalysisConfig],
    price_field: Optional[str],
    timestamp_field: Optional[str],
) -> List[RegimeInterval]:
    cfg = config or RegimeAnalysisConfig()
    cfg.validate()
    parsed = _parse_records(records, price_field, timestamp_field)
    if not parsed:
        return []

    prices = [price for _, price in parsed]
    thresholds = _resolved_thresholds(prices, cfg)
    rolling_volatility = _rolling_volatility(prices, cfg.rolling_window_intervals)

    intervals: List[RegimeInterval] = []
    consecutive_high = 0
    for index, (timestamp, price) in enumerate(parsed):
        if price >= thresholds["high_price_threshold"]:
            consecutive_high += 1
        else:
            consecutive_high = 0

        regime = classify_interval(
            price=price,
            config=cfg,
            high_price_threshold=thresholds["high_price_threshold"],
            spike_price_threshold=thresholds["spike_price_threshold"],
            rolling_volatility=rolling_volatility[index],
            volatility_threshold=thresholds["volatility_threshold"],
            consecutive_high_intervals=consecutive_high,
        )
        intervals.append(
            RegimeInterval(
                index=index,
                timestamp=timestamp,
                price=price,
                rolling_volatility=rolling_volatility[index],
                consecutive_high_intervals=consecutive_high,
                regime=regime,
            )
        )
    return intervals


def _parse_records(
    records: Sequence[Any],
    price_field: Optional[str],
    timestamp_field: Optional[str],
) -> List[Tuple[Optional[datetime], float]]:
    parsed = []
    for record in records:
        timestamp = _extract_timestamp(record, timestamp_field)
        price = _extract_price(record, price_field)
        parsed.append((timestamp, price))
    return parsed


def _extract_price(record: Any, price_field: Optional[str]) -> float:
    if isinstance(record, (int, float)):
        return float(record)

    candidate_fields = [price_field] if price_field else [
        "price",
        "rrp",
        "RRP",
        "price_per_mwh",
        "price_per_kwh",
    ]
    for field in candidate_fields:
        if field is None:
            continue
        if isinstance(record, dict) and field in record:
            return float(record[field])
        if hasattr(record, field):
            return float(getattr(record, field))
    raise ValueError("could not extract price from record")


def _extract_timestamp(record: Any, timestamp_field: Optional[str]) -> Optional[datetime]:
    candidate_fields = [timestamp_field] if timestamp_field else [
        "timestamp",
        "settlementdate",
        "SETTLEMENTDATE",
    ]
    for field in candidate_fields:
        if field is None:
            continue
        value = None
        if isinstance(record, dict) and field in record:
            value = record[field]
        elif hasattr(record, field):
            value = getattr(record, field)
        if value is None:
            continue
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
    return None


def _resolved_thresholds(prices: Sequence[float], config: RegimeAnalysisConfig) -> Dict[str, float]:
    volatility_values = [
        value for value in _rolling_volatility(prices, config.rolling_window_intervals)
        if value is not None
    ]
    if not volatility_values:
        volatility_values = [0.0]

    return {
        "high_price_threshold": _first_not_none(
            config.high_price_threshold,
            _percentile(prices, config.high_price_percentile),
        ),
        "spike_price_threshold": _first_not_none(
            config.spike_price_threshold,
            _percentile(prices, config.spike_price_percentile),
        ),
        "volatility_threshold": _first_not_none(
            config.volatility_threshold,
            _percentile(volatility_values, config.volatility_percentile),
        ),
    }


def _rolling_volatility(prices: Sequence[float], window: int) -> List[Optional[float]]:
    values: List[Optional[float]] = []
    for index in range(len(prices)):
        start = max(0, index - window + 1)
        sample = prices[start:index + 1]
        if len(sample) < 2:
            values.append(None)
        else:
            values.append(pstdev(sample))
    return values


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot calculate percentile for empty values")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = percentile * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction


def _frequency_by_regime(intervals: Sequence[RegimeInterval]) -> Dict[str, Dict[str, float]]:
    counts = Counter(interval.regime for interval in intervals)
    total = len(intervals)
    return {
        regime: {
            "count": counts.get(regime, 0),
            "share": counts.get(regime, 0) / total if total else 0.0,
        }
        for regime in REGIMES
    }


def _average_price_by_regime(intervals: Sequence[RegimeInterval]) -> Dict[str, Optional[float]]:
    prices_by_regime: Dict[str, List[float]] = defaultdict(list)
    for interval in intervals:
        prices_by_regime[interval.regime].append(interval.price)
    return {
        regime: mean(prices_by_regime[regime]) if prices_by_regime[regime] else None
        for regime in REGIMES
    }


def _average_duration_by_regime(
    intervals: Sequence[RegimeInterval],
    interval_hours: float,
) -> Dict[str, Optional[float]]:
    durations_by_regime: Dict[str, List[float]] = defaultdict(list)
    for regime, length in _regime_runs(intervals):
        durations_by_regime[regime].append(length * interval_hours)
    return {
        regime: mean(durations_by_regime[regime]) if durations_by_regime[regime] else None
        for regime in REGIMES
    }


def _transition_statistics(intervals: Sequence[RegimeInterval]) -> Dict[str, Any]:
    transition_counts: Counter = Counter()
    for previous, current in zip(intervals, intervals[1:]):
        if previous.regime != current.regime:
            transition_counts[(previous.regime, current.regime)] += 1

    total = sum(transition_counts.values())
    return {
        "total_transitions": total,
        "counts": {
            f"{source}->{target}": count
            for (source, target), count in sorted(transition_counts.items())
        },
        "probabilities": {
            f"{source}->{target}": count / total if total else 0.0
            for (source, target), count in sorted(transition_counts.items())
        },
    }


def _regime_runs(intervals: Sequence[RegimeInterval]) -> List[Tuple[str, int]]:
    if not intervals:
        return []

    runs: List[Tuple[str, int]] = []
    current_regime = intervals[0].regime
    current_length = 1
    for interval in intervals[1:]:
        if interval.regime == current_regime:
            current_length += 1
        else:
            runs.append((current_regime, current_length))
            current_regime = interval.regime
            current_length = 1
    runs.append((current_regime, current_length))
    return runs


def _day_from_intervals(intervals: Sequence[RegimeInterval]) -> Optional[date]:
    for interval in intervals:
        if interval.timestamp is not None:
            return interval.timestamp.date()
    return None


def _first_not_none(*values: Optional[float]) -> Optional[float]:
    for value in values:
        if value is not None:
            return value
    return None
