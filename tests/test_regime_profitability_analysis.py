"""Tests for profitability analysis by market regime."""

import pytest

from src.regime_analysis import (
    NEGATIVE_PRICING,
    NORMAL,
    PRICE_SPIKE,
    RegimeAnalysisConfig,
)
from src.regime_profitability_analysis import (
    RegimeProfitabilityConfig,
    cycles_by_regime,
    degradation_by_regime,
    export_activity_by_regime,
    profitability_by_regime,
)


def test_profitability_by_regime_aggregates_required_outputs():
    rows = [
        {"price_per_kwh": 0.04, "cashflow": -0.05, "energy_kwh": 1.0, "degradation_cost": 0.01},
        {
            "price_per_kwh": 0.50,
            "cashflow": 1.00,
            "energy_kwh": -2.0,
            "degradation_cost": 0.02,
            "spread_captured": 0.46,
        },
        {"price_per_kwh": -0.02, "cashflow": 0.01, "energy_kwh": 1.0, "degradation_cost": 0.01},
        {
            "price_per_kwh": 0.55,
            "cashflow": 1.20,
            "energy_kwh": -2.0,
            "degradation_cost": 0.02,
            "spread_captured": 0.50,
        },
    ]
    regimes = [NORMAL, PRICE_SPIKE, NEGATIVE_PRICING, PRICE_SPIKE]
    config = RegimeProfitabilityConfig(battery_capacity_energy=10.0)

    summary = profitability_by_regime(rows, regimes, profitability_config=config)
    spike = summary["by_regime"][PRICE_SPIKE]

    assert spike["average_profit"] == pytest.approx(1.10)
    assert spike["average_spread_captured"] == pytest.approx(0.48)
    assert spike["energy_exported"] == pytest.approx(4.0)
    assert spike["cycle_contribution"] == pytest.approx(0.4)
    assert spike["degradation_contribution"] == pytest.approx(0.04)
    assert spike["profitability_share"] == pytest.approx(2.20 / 2.16)
    assert PRICE_SPIKE in summary["profitable_regimes"]
    assert summary["top_pnl_regimes"][0] == PRICE_SPIKE


def test_helpers_return_focused_views():
    rows = [
        {"price": 30.0, "profit": -3.0, "charged_mwh": 1.0, "degradation_cost": 1.0},
        {"price": 300.0, "profit": 20.0, "exported_mwh": 2.0, "degradation_cost": 2.0},
    ]
    regimes = [NORMAL, PRICE_SPIKE]
    config = RegimeProfitabilityConfig(battery_capacity_energy=10.0)

    cycles = cycles_by_regime(rows, regimes, profitability_config=config)
    exports = export_activity_by_regime(rows, regimes, profitability_config=config)
    degradation = degradation_by_regime(rows, regimes, profitability_config=config)

    assert cycles[NORMAL] == pytest.approx(0.1)
    assert cycles[PRICE_SPIKE] == pytest.approx(0.2)
    assert exports[PRICE_SPIKE]["energy_exported"] == pytest.approx(2.0)
    assert exports[PRICE_SPIKE]["export_interval_count"] == 1
    assert degradation[NORMAL]["degradation_contribution"] == pytest.approx(1.0)


def test_degradation_dominated_regime_is_identified():
    rows = [
        {
            "price": 100.0,
            "profit": 0.50,
            "exported_energy": 1.0,
            "degradation_cost": 2.0,
        }
    ]

    summary = profitability_by_regime(rows, [NORMAL])

    assert summary["by_regime"][NORMAL]["degradation_dominates"] is True
    assert NORMAL in summary["degradation_dominated_regimes"]


def test_can_classify_regimes_from_dispatch_prices_when_not_supplied():
    rows = [
        {"price": 50.0, "profit": 0.0},
        {"price": -10.0, "profit": 1.0},
        {"price": 500.0, "profit": 10.0, "exported_energy": 1.0},
    ]
    regime_config = RegimeAnalysisConfig(
        high_price_threshold=100.0,
        spike_price_threshold=400.0,
        volatility_threshold=1000.0,
    )

    summary = profitability_by_regime(rows, regime_config=regime_config)

    assert summary["by_regime"][NEGATIVE_PRICING]["interval_count"] == 1
    assert summary["by_regime"][PRICE_SPIKE]["total_profit"] == pytest.approx(10.0)


def test_explicit_spread_field_overrides_estimated_spread():
    rows = [
        {"price": 10.0, "profit": -1.0, "charged_energy": 1.0, "captured_spread": 5.0},
        {"price": 50.0, "profit": 3.0, "exported_energy": 1.0, "captured_spread": 7.0},
    ]

    summary = profitability_by_regime(rows, [NORMAL, NORMAL])

    assert summary["by_regime"][NORMAL]["average_spread_captured"] == pytest.approx(6.0)


def test_degradation_can_be_estimated_from_throughput():
    rows = [
        {"price": 50.0, "profit": -1.0, "energy_kwh": 2.0},
        {"price": 200.0, "profit": 4.0, "energy_kwh": -3.0},
    ]
    config = RegimeProfitabilityConfig(degradation_cost_per_energy=0.10)

    summary = profitability_by_regime(rows, [NORMAL, PRICE_SPIKE], profitability_config=config)

    assert summary["by_regime"][NORMAL]["degradation_contribution"] == pytest.approx(0.2)
    assert summary["by_regime"][PRICE_SPIKE]["degradation_contribution"] == pytest.approx(0.3)


def test_regime_length_must_match_dispatch_results():
    rows = [{"price": 50.0, "profit": 0.0}]

    with pytest.raises(ValueError):
        profitability_by_regime(rows, [NORMAL, PRICE_SPIKE])


def test_empty_dispatch_results_raise_value_error():
    with pytest.raises(ValueError):
        profitability_by_regime([])
