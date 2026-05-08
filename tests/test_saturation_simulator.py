"""Tests for analytical battery saturation simulator."""

import pytest

from src.regime_analysis import NORMAL, PRICE_SPIKE, SUSTAINED_HIGH_PRICE_EVENT, VOLATILE
from src.saturation_simulator import (
    SaturationConfig,
    compare_participation_levels,
    profitability_decay_vs_participation,
    simulate_saturation,
)


def test_single_battery_case_preserves_realised_profit():
    rows = [
        {
            "regime": PRICE_SPIKE,
            "profit": 100.0,
            "degradation_cost": 5.0,
            "exported_energy": 10.0,
            "spread_captured": 0.50,
        }
    ]

    result = simulate_saturation(rows, config=SaturationConfig(number_batteries=1))

    assert result["single_battery_profit"] == pytest.approx(100.0)
    assert result["per_battery_profit"] == pytest.approx(100.0)
    assert result["fleet_profit"] == pytest.approx(100.0)
    assert result["profit_decay"] == pytest.approx(0.0)
    assert result["volatility_compression"] == pytest.approx(0.0)


def test_multi_battery_participation_compresses_spike_profit():
    rows = [
        {
            "regime": PRICE_SPIKE,
            "profit": 100.0,
            "degradation_cost": 5.0,
            "exported_energy": 10.0,
            "spread_captured": 0.50,
        }
    ]
    config = SaturationConfig(
        number_batteries=5,
        reaction_aggressiveness=1.0,
        spread_compression_factor=0.10,
        export_window_competition_factor=0.0,
    )

    result = simulate_saturation(rows, config=config)

    assert result["per_battery_profit"] < result["single_battery_profit"]
    assert result["profit_decay"] == pytest.approx(0.42)
    assert result["adjusted_rows"][0]["spread_capture_multiplier"] == pytest.approx(0.60)
    assert result["regime_profitability"]["by_regime"][PRICE_SPIKE]["total_profit"] == pytest.approx(58.0)


def test_export_window_competition_reduces_exported_energy_and_degradation():
    rows = [
        {
            "regime": VOLATILE,
            "profit": 50.0,
            "degradation_cost": 10.0,
            "exported_energy": 10.0,
        }
    ]
    config = SaturationConfig(
        number_batteries=11,
        reaction_aggressiveness=1.0,
        spread_compression_factor=0.0,
        export_window_competition_factor=0.10,
    )

    result = simulate_saturation(rows, config=config)

    assert result["export_window_competition"] == pytest.approx(0.5)
    assert result["adjusted_rows"][0]["exported_energy"] == pytest.approx(5.0)
    assert result["per_battery_degradation"] == pytest.approx(5.0)


def test_normal_regime_is_not_compressed_by_default():
    rows = [
        {"regime": NORMAL, "profit": 10.0, "degradation_cost": 2.0, "exported_energy": 1.0},
        {"regime": PRICE_SPIKE, "profit": 10.0, "degradation_cost": 2.0, "exported_energy": 1.0},
    ]
    config = SaturationConfig(
        number_batteries=3,
        spread_compression_factor=0.25,
        export_window_competition_factor=0.0,
    )

    result = simulate_saturation(rows, config=config)

    normal_row, spike_row = result["adjusted_rows"]
    assert normal_row["profit"] == pytest.approx(10.0)
    assert spike_row["profit"] < 10.0


def test_compare_participation_levels_returns_decay_curve():
    rows = [
        {"regime": PRICE_SPIKE, "profit": 100.0, "degradation_cost": 0.0, "exported_energy": 10.0},
    ]
    config = SaturationConfig(spread_compression_factor=0.05)

    comparison = compare_participation_levels(rows, [1, 5, 10], config)
    curve = comparison["profit_decay_curve"]

    assert [point["number_batteries"] for point in curve] == [1, 5, 10]
    assert curve[0]["profit_decay"] == pytest.approx(0.0)
    assert curve[1]["profit_decay"] < curve[2]["profit_decay"]
    assert comparison["most_saturated_case"]["number_batteries"] == 10


def test_profitability_decay_vs_participation_is_focused_curve():
    rows = [
        {"regime": SUSTAINED_HIGH_PRICE_EVENT, "profit": 20.0, "degradation_cost": 1.0, "exported_energy": 2.0},
    ]

    curve = profitability_decay_vs_participation(rows, [1, 2])

    assert len(curve) == 2
    assert set(curve[0]) >= {
        "number_batteries",
        "per_battery_profit",
        "fleet_profit",
        "profit_decay",
        "volatility_compression",
    }


def test_regimes_can_be_supplied_separately():
    rows = [
        {"profit": 20.0, "degradation_cost": 1.0, "exported_energy": 2.0},
    ]

    result = simulate_saturation(rows, regime_intervals=[PRICE_SPIKE])

    assert result["regime_profitability"]["by_regime"][PRICE_SPIKE]["interval_count"] == 1


def test_invalid_config_raises_value_error():
    rows = [{"regime": PRICE_SPIKE, "profit": 1.0}]
    config = SaturationConfig(number_batteries=0)

    with pytest.raises(ValueError):
        simulate_saturation(rows, config=config)


def test_rows_without_regime_require_regime_intervals():
    rows = [{"profit": 1.0}]

    with pytest.raises(ValueError):
        simulate_saturation(rows)
