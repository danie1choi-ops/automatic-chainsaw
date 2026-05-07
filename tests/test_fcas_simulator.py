"""Unit tests for the simplified FCAS simulator."""

import pytest

from src.fcas_simulator import (
    FCASActivationEvent,
    FCASSimulatorConfig,
    average_price,
    compare_revenue_cases,
    format_comparison_summary,
    simulate_arbitrage_only,
    simulate_fcas_only,
    simulate_stacked_revenue,
)


def test_compare_revenue_cases_returns_all_scenarios():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        annualise_results=False,
    )
    prices = [40.0, 45.0, 180.0, 200.0]

    results = compare_revenue_cases(prices, config)

    assert set(results) == {"arbitrage_only", "fcas_only", "stacked_revenue"}
    assert results["arbitrage_only"].annual_revenue > 0
    assert results["fcas_only"].annual_revenue > 0
    assert results["stacked_revenue"].revenue_breakdown.fcas_enablement_revenue > 0


def test_stacked_arbitrage_is_limited_by_fcas_reservation():
    prices = [40.0] * 6 + [200.0] * 6
    no_reserve = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        fcas_reservation_percent=0.0,
        annualise_results=False,
    )
    with_reserve = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        fcas_reservation_percent=50.0,
        annualise_results=False,
    )

    arbitrage_only = simulate_stacked_revenue(prices, no_reserve)
    stacked = simulate_stacked_revenue(prices, with_reserve)

    assert stacked.revenue_breakdown.arbitrage_revenue < arbitrage_only.revenue_breakdown.arbitrage_revenue
    assert stacked.revenue_breakdown.fcas_enablement_revenue > 0


def test_fcas_only_enablement_uses_fixed_availability_payment():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        fcas_reservation_percent=20.0,
        fcas_availability_price_per_mw_hour=10.0,
        interval_hours=0.5,
        annualise_results=False,
    )

    result = simulate_fcas_only([100.0, 100.0], config)

    assert result.revenue_breakdown.fcas_enablement_revenue == pytest.approx(100.0)
    assert result.annual_revenue == pytest.approx(100.0)
    assert result.cycles == 0


def test_activation_event_adds_revenue_and_cycles():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        fcas_reservation_percent=20.0,
        interval_hours=0.5,
        round_trip_efficiency=1.0,
        annualise_results=False,
    )
    events = [
        FCASActivationEvent(
            interval_index=0,
            direction="raise",
            mw=10.0,
            duration_hours=0.5,
            price_per_mwh=200.0,
        )
    ]

    result = simulate_fcas_only([100.0], config, events)

    assert result.revenue_breakdown.fcas_activation_revenue == pytest.approx(1000.0)
    assert result.cycles == pytest.approx(5.0 / 200.0)
    assert result.ending_soc_mwh == pytest.approx(45.0)


def test_activation_event_is_capped_to_reserved_mw():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        fcas_reservation_percent=10.0,
        interval_hours=1.0,
        round_trip_efficiency=1.0,
        annualise_results=False,
    )
    events = [
        FCASActivationEvent(interval_index=0, direction="raise", mw=50.0, duration_hours=1.0)
    ]

    result = simulate_fcas_only([100.0], config, events)

    assert result.revenue_breakdown.fcas_activation_revenue == pytest.approx(500.0)
    assert result.warnings


def test_degradation_cost_reduces_net_revenue():
    prices = [40.0, 200.0]
    no_degradation = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        interval_hours=1.0,
        round_trip_efficiency=1.0,
        degradation_cost_per_mwh=0.0,
        annualise_results=False,
    )
    with_degradation = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        interval_hours=1.0,
        round_trip_efficiency=1.0,
        degradation_cost_per_mwh=10.0,
        annualise_results=False,
    )

    clean = simulate_arbitrage_only(prices, no_degradation)
    degraded = simulate_arbitrage_only(prices, with_degradation)

    assert degraded.degradation_cost > 0
    assert degraded.annual_revenue < clean.annual_revenue


def test_results_can_be_annualised():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        fcas_reservation_percent=20.0,
        fcas_availability_price_per_mw_hour=10.0,
        interval_hours=1.0,
        annualise_results=True,
    )

    result = simulate_fcas_only([100.0], config)

    assert result.annual_revenue == pytest.approx(10.0 * 10.0 * 8760.0)
    assert result.assumptions["annualisation_factor"] == pytest.approx(8760.0)


def test_invalid_config_raises_value_error():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=0.0,
        max_power_mw=50.0,
    )

    with pytest.raises(ValueError):
        simulate_arbitrage_only([100.0], config)


def test_helpers_format_and_average_prices():
    config = FCASSimulatorConfig(
        battery_capacity_mwh=100.0,
        max_power_mw=50.0,
        annualise_results=False,
    )
    results = compare_revenue_cases([40.0, 200.0], config)

    summary = format_comparison_summary(results)

    assert "scenario,annual_revenue,cycles,degradation_cost,utilisation" in summary
    assert average_price([40.0, 200.0]) == pytest.approx(120.0)
