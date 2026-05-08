"""Tests for historical price regime analysis."""

from datetime import datetime, timedelta

import pytest

from src.data_loader import PricePoint
from src.regime_analysis import (
    NEGATIVE_PRICING,
    NORMAL,
    PRICE_SPIKE,
    SUSTAINED_HIGH_PRICE_EVENT,
    VOLATILE,
    RegimeAnalysisConfig,
    classify_day,
    classify_interval,
    summarise_regimes,
)


def test_classify_interval_priority_rules():
    config = RegimeAnalysisConfig(sustained_high_intervals=3)

    assert classify_interval(
        price=-10.0,
        config=config,
        high_price_threshold=100.0,
        spike_price_threshold=200.0,
        rolling_volatility=500.0,
        volatility_threshold=20.0,
        consecutive_high_intervals=5,
    ) == NEGATIVE_PRICING

    assert classify_interval(
        price=250.0,
        config=config,
        high_price_threshold=100.0,
        spike_price_threshold=200.0,
        rolling_volatility=500.0,
        volatility_threshold=20.0,
        consecutive_high_intervals=5,
    ) == PRICE_SPIKE

    assert classify_interval(
        price=150.0,
        config=config,
        high_price_threshold=100.0,
        spike_price_threshold=200.0,
        rolling_volatility=500.0,
        volatility_threshold=20.0,
        consecutive_high_intervals=3,
    ) == SUSTAINED_HIGH_PRICE_EVENT

    assert classify_interval(
        price=80.0,
        config=config,
        high_price_threshold=100.0,
        spike_price_threshold=200.0,
        rolling_volatility=50.0,
        volatility_threshold=20.0,
    ) == VOLATILE

    assert classify_interval(
        price=80.0,
        config=config,
        high_price_threshold=100.0,
        spike_price_threshold=200.0,
        rolling_volatility=5.0,
        volatility_threshold=20.0,
    ) == NORMAL


def test_summarise_regimes_outputs_required_metrics():
    prices = [
        50.0,
        52.0,
        -20.0,
        55.0,
        300.0,
        130.0,
        140.0,
        150.0,
        60.0,
        65.0,
    ]
    config = RegimeAnalysisConfig(
        high_price_threshold=100.0,
        spike_price_threshold=250.0,
        volatility_threshold=1000.0,
        sustained_high_intervals=4,
        interval_hours=5.0 / 60.0,
    )

    summary = summarise_regimes(prices, config)

    assert summary["interval_count"] == len(prices)
    assert summary["frequency"][NEGATIVE_PRICING]["count"] == 1
    assert summary["frequency"][PRICE_SPIKE]["count"] == 1
    assert summary["frequency"][SUSTAINED_HIGH_PRICE_EVENT]["count"] == 1
    assert summary["average_duration_hours"][SUSTAINED_HIGH_PRICE_EVENT] == pytest.approx(5.0 / 60.0)
    assert summary["average_price_by_regime"][PRICE_SPIKE] == pytest.approx(300.0)
    assert summary["transitions"]["total_transitions"] > 0
    assert "normal->negative_pricing" in summary["transitions"]["counts"]


def test_percentile_thresholds_are_resolved_from_series():
    prices = [10.0, 20.0, 30.0, 40.0, 500.0]
    config = RegimeAnalysisConfig(
        high_price_percentile=0.75,
        spike_price_percentile=1.0,
        volatility_threshold=1000.0,
    )

    summary = summarise_regimes(prices, config)

    assert summary["thresholds"]["high_price_threshold"] == pytest.approx(40.0)
    assert summary["thresholds"]["spike_price_threshold"] == pytest.approx(500.0)
    assert summary["frequency"][PRICE_SPIKE]["count"] == 1


def test_rolling_volatility_can_classify_intervals():
    prices = [50.0, 52.0, 48.0, 200.0, 10.0, 210.0]
    config = RegimeAnalysisConfig(
        high_price_threshold=1000.0,
        spike_price_threshold=2000.0,
        volatility_threshold=40.0,
        rolling_window_intervals=3,
    )

    summary = summarise_regimes(prices, config)

    assert summary["frequency"][VOLATILE]["count"] > 0
    assert all(
        interval.regime != PRICE_SPIKE
        for interval in summary["classified_intervals"]
    )


def test_classify_day_accepts_price_points_and_returns_dominant_regime():
    start = datetime(2026, 5, 1, 0, 0)
    records = [
        PricePoint(start + timedelta(minutes=5 * index), "QLD1", price)
        for index, price in enumerate([0.05, 0.06, -0.01, 0.07])
    ]
    config = RegimeAnalysisConfig(
        high_price_threshold=1.0,
        spike_price_threshold=2.0,
        volatility_threshold=1.0,
    )

    day = classify_day(records, config)

    assert day["date"] == start.date()
    assert day["dominant_regime"] == NORMAL
    assert day["frequency"][NEGATIVE_PRICING]["count"] == 1


def test_transition_statistics_count_regime_changes_only():
    prices = [10.0, 10.0, -5.0, -6.0, 300.0, 20.0]
    config = RegimeAnalysisConfig(
        high_price_threshold=100.0,
        spike_price_threshold=250.0,
        volatility_threshold=1000.0,
    )

    summary = summarise_regimes(prices, config)

    assert summary["transitions"]["total_transitions"] == 3
    assert summary["transitions"]["counts"]["normal->negative_pricing"] == 1
    assert summary["transitions"]["counts"]["negative_pricing->price_spike"] == 1
    assert summary["transitions"]["counts"]["price_spike->normal"] == 1


def test_empty_series_raises_value_error():
    with pytest.raises(ValueError):
        summarise_regimes([])


def test_invalid_config_raises_value_error():
    config = RegimeAnalysisConfig(high_price_percentile=1.5)

    with pytest.raises(ValueError):
        summarise_regimes([1.0, 2.0, 3.0], config)
