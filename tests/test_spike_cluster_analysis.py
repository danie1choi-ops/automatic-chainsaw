"""Tests for clustered price-spike analysis."""

from datetime import datetime, timedelta

import pytest

from src.spike_cluster_analysis import (
    SpikeClusterAnalysisConfig,
    analyse_spike_clusters,
    load_output_rows,
    summarise_spike_clusters,
)


def _row(index, price, action="HOLD", soc=50.0, cashflow=0.0, energy_kwh=0.0):
    return {
        "timestamp": (datetime(2026, 5, 1, 18, 0) + timedelta(minutes=5 * index)).isoformat(),
        "price_per_kwh": price,
        "action": action,
        "soc_percent": soc,
        "cashflow": cashflow,
        "energy_kwh": energy_kwh,
        "reason": "Battery below min SoC" if soc <= 20 and action != "EXPORT" else "",
    }


def test_detects_near_consecutive_spike_clusters_and_metrics():
    rows = [
        _row(0, 0.10),
        _row(1, 0.30, "EXPORT", 46.91, 0.1042, -0.417),
        _row(2, 0.12),
        _row(3, 0.50, "EXPORT", 43.82, 0.1875, -0.417),
        _row(4, 0.40, "HOLD", 20.0, 0.0),
        _row(5, 0.10),
    ]
    config = SpikeClusterAnalysisConfig(
        spike_price_threshold=0.24,
        max_gap_intervals=1,
        min_cluster_size=2,
        battery_capacity_kwh=13.5,
        max_discharge_kw=5.0,
        interval_hours=5.0 / 60.0,
        degradation_cost_per_kwh=0.05,
    )

    clusters = analyse_spike_clusters(rows, config)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.start_timestamp == datetime(2026, 5, 1, 18, 5)
    assert cluster.end_timestamp == datetime(2026, 5, 1, 18, 20)
    assert cluster.spike_interval_count == 3
    assert cluster.max_price == pytest.approx(0.50)
    assert cluster.average_spike_price == pytest.approx((0.30 + 0.50 + 0.40) / 3)
    assert cluster.first_export_timestamp == datetime(2026, 5, 1, 18, 5)
    assert cluster.last_export_timestamp == datetime(2026, 5, 1, 18, 15)
    assert cluster.starting_soc == pytest.approx(50.0, abs=0.01)
    assert cluster.ending_soc == pytest.approx(20.0)
    assert cluster.export_count == 2
    assert cluster.missed_spike_exports_due_to_min_soc == 1
    assert cluster.realised_cashflow == pytest.approx(0.2917)
    assert cluster.theoretical_cashflow_if_reserved == pytest.approx(0.4375)


def test_min_cluster_size_filters_single_spikes():
    rows = [
        _row(0, 0.30),
        _row(1, 0.10),
        _row(2, 0.50),
    ]
    config = SpikeClusterAnalysisConfig(max_gap_intervals=0, min_cluster_size=2)

    assert analyse_spike_clusters(rows, config) == []


def test_clusters_do_not_bridge_source_files():
    first = _row(0, 0.30)
    first["source_file"] = "outputs/backtest_results.csv"
    second = _row(1, 0.50)
    second["source_file"] = "outputs/live_observation.csv"
    config = SpikeClusterAnalysisConfig(max_gap_intervals=0, min_cluster_size=2)

    assert analyse_spike_clusters([first, second], config) == []


def test_summarise_spike_clusters_returns_required_metrics():
    rows = [
        _row(0, 0.30, "EXPORT", 46.91, 0.1042, -0.417),
        _row(1, 0.50, "EXPORT", 43.82, 0.1875, -0.417),
        _row(2, 0.40, "HOLD", 20.0, 0.0),
    ]
    config = SpikeClusterAnalysisConfig(
        spike_price_threshold=0.24,
        min_cluster_size=2,
        max_gap_intervals=0,
        battery_capacity_kwh=13.5,
        max_discharge_kw=5.0,
        interval_hours=5.0 / 60.0,
        degradation_cost_per_kwh=0.05,
    )

    summary = summarise_spike_clusters(rows, config)

    assert summary["total_clusters"] == 1
    assert summary["average_cluster_duration_hours"] == pytest.approx(15.0 / 60.0)
    assert summary["average_soc_drawdown"] == pytest.approx(30.0, abs=0.01)
    assert summary["missed_spike_count"] == 1
    assert summary["estimated_missed_cashflow"] == pytest.approx(0.1458, abs=0.0001)
    assert summary["percentage_clusters_ending_at_min_soc"] == pytest.approx(100.0)


def test_live_observation_schema_uses_regime_and_simulated_fields():
    rows = [
        {
            "timestamp": "2026-05-12T20:47:29",
            "price": "0.254726",
            "regime": "price_spike",
            "action": "EXPORT",
            "simulated_soc": "46.91",
            "simulated_cashflow": "0.085302",
            "reason": "Price at or above export threshold",
        },
        {
            "timestamp": "2026-05-12T20:52:29",
            "price": "0.108958",
            "regime": "normal",
            "action": "HOLD",
            "simulated_soc": "46.91",
            "simulated_cashflow": "0.000000",
            "reason": "No price signal",
        },
        {
            "timestamp": "2026-05-12T20:57:29",
            "price": "0.133045",
            "regime": "price_spike",
            "action": "HOLD",
            "simulated_soc": "20.00",
            "simulated_cashflow": "0.000000",
            "reason": "Battery below min SoC",
        },
    ]
    config = SpikeClusterAnalysisConfig(max_gap_intervals=1, min_cluster_size=2)

    clusters = analyse_spike_clusters(rows, config)

    assert len(clusters) == 1
    assert clusters[0].missed_spike_exports_due_to_min_soc == 1
    assert clusters[0].realised_cashflow == pytest.approx(0.085302)


def test_empty_summary_is_zeroed():
    summary = summarise_spike_clusters([])

    assert summary == {
        "total_clusters": 0,
        "average_cluster_duration_hours": 0.0,
        "average_soc_drawdown": 0.0,
        "missed_spike_count": 0,
        "estimated_missed_cashflow": 0.0,
        "percentage_clusters_ending_at_min_soc": 0.0,
    }


def test_load_output_rows_reads_csv(tmp_path):
    path = tmp_path / "backtest_results.csv"
    path.write_text(
        "timestamp,price_per_kwh,action,soc_percent,cashflow\n"
        "2026-05-01T00:00:00,0.30,EXPORT,45.0,0.1\n"
    )

    rows = load_output_rows(path)

    assert rows[0]["price_per_kwh"] == "0.30"
