"""Tests for live observation summary reporting."""

import pytest

from src.live_summary import (
    render_markdown_report,
    summarise_live_observations,
    write_markdown_report,
)


def test_summarise_live_observations_calculates_required_metrics():
    rows = [
        {
            "timestamp": "2026-05-01T18:00:00",
            "price": "0.30",
            "regime": "price_spike",
            "action": "EXPORT",
            "simulated_soc": "46.91",
            "simulated_cashflow": "0.1042",
            "reason": "Price at or above export threshold",
        },
        {
            "timestamp": "2026-05-01T18:05:00",
            "price": "0.50",
            "regime": "price_spike",
            "action": "EXPORT",
            "simulated_soc": "43.82",
            "simulated_cashflow": "0.1875",
            "reason": "Price at or above export threshold",
        },
        {
            "timestamp": "2026-05-01T18:10:00",
            "price": "0.12",
            "regime": "normal",
            "action": "HOLD",
            "simulated_soc": "43.82",
            "simulated_cashflow": "0.0000",
            "reason": "No price signal",
        },
        {
            "timestamp": "2026-05-01T18:15:00",
            "price": "-0.02",
            "regime": "negative_pricing",
            "action": "CHARGE",
            "simulated_soc": "46.91",
            "simulated_cashflow": "-0.0120",
            "reason": "Negative price",
        },
        {
            "timestamp": "2026-05-01T18:20:00",
            "price": "0.25",
            "regime": "price_spike",
            "action": "HOLD",
            "simulated_soc": "20.00",
            "simulated_cashflow": "0.0000",
            "reason": "Battery below min SoC",
        },
    ]

    summary = summarise_live_observations(rows)

    assert summary.total_intervals_observed == 5
    assert summary.regime_frequencies == {
        "price_spike": 3,
        "normal": 1,
        "negative_pricing": 1,
    }
    assert summary.export_actions == 2
    assert summary.hold_actions == 2
    assert summary.average_spike_price == pytest.approx(0.35)
    assert summary.highest_observed_price == pytest.approx(0.50)
    assert summary.total_simulated_cashflow == pytest.approx(0.2797)
    assert summary.average_soc == pytest.approx(40.292)
    assert summary.minimum_soc_reached == pytest.approx(20.0)
    assert summary.longest_spike_cluster == 2
    assert summary.percentage_exports_during_price_spike == pytest.approx(100.0)
    assert summary.exports_concentrated_in_spike_regimes is True
    assert summary.soc_exhaustion_occurred is True
    assert summary.normal_periods_generated_meaningful_activity is False


def test_markdown_report_contains_findings_and_can_be_written(tmp_path):
    summary = summarise_live_observations(
        [
            {
                "timestamp": "2026-05-01T18:00:00",
                "price": "0.30",
                "regime": "price_spike",
                "action": "EXPORT",
                "simulated_soc": "46.91",
                "simulated_cashflow": "0.1042",
                "reason": "Price at or above export threshold",
            }
        ]
    )
    report_path = tmp_path / "live_summary.md"

    write_markdown_report(summary, report_path)
    report = report_path.read_text()

    assert report == render_markdown_report(summary)
    assert "# Live Observation Summary" in report
    assert "## Findings" in report
    assert "Exports remained concentrated in spike regimes" in report
