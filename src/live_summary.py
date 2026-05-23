"""Summarise live observation output.

This module is analytical only. It reads observations produced by live-observe
mode and writes aggregate reporting; it does not change strategy or dispatch
logic.
"""

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from src import config
from src.regime_analysis import PRICE_SPIKE


LIVE_OBSERVATION_INPUT = Path("outputs/live_observation.csv")
LIVE_SUMMARY_OUTPUT = Path("outputs/live_summary.md")


@dataclass(frozen=True)
class LiveObservationSummary:
    """Aggregate metrics for live-observation rows."""

    total_intervals_observed: int
    regime_frequencies: Dict[str, int]
    export_actions: int
    hold_actions: int
    average_spike_price: float
    highest_observed_price: float
    total_simulated_cashflow: float
    average_soc: float
    minimum_soc_reached: float
    longest_spike_cluster: int
    percentage_exports_during_price_spike: float
    exports_concentrated_in_spike_regimes: bool
    soc_exhaustion_occurred: bool
    normal_period_activity_count: int
    normal_period_cashflow: float
    normal_periods_generated_meaningful_activity: bool


def load_live_observations(path: Path | str = LIVE_OBSERVATION_INPUT) -> List[Dict[str, str]]:
    """Read live observation CSV rows."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def summarise_live_observations(rows: List[Dict[str, str]]) -> LiveObservationSummary:
    """Calculate summary statistics and analytical findings."""
    total_intervals = len(rows)
    regime_frequencies = Counter(_text(row, "regime") for row in rows)
    actions = [_text(row, "action").upper() for row in rows]
    prices = [_number(row, "price") for row in rows]
    soc_values = [_number(row, "simulated_soc") for row in rows]
    cashflows = [_number(row, "simulated_cashflow") for row in rows]
    spike_rows = [row for row in rows if _text(row, "regime") == PRICE_SPIKE]
    spike_prices = [_number(row, "price") for row in spike_rows]
    export_rows = [
        row for row in rows if _text(row, "action").upper() == "EXPORT"
    ]
    spike_export_count = sum(
        1 for row in export_rows if _text(row, "regime") == PRICE_SPIKE
    )
    normal_activity_rows = [
        row
        for row in rows
        if _text(row, "regime") == "normal"
        and (
            _text(row, "action").upper() != "HOLD"
            or abs(_number(row, "simulated_cashflow")) > 0.000001
        )
    ]
    normal_cashflow = sum(
        _number(row, "simulated_cashflow")
        for row in rows
        if _text(row, "regime") == "normal"
    )

    export_count = len(export_rows)
    export_spike_percentage = (
        spike_export_count / export_count * 100.0 if export_count else 0.0
    )
    min_soc = min(soc_values) if soc_values else 0.0

    return LiveObservationSummary(
        total_intervals_observed=total_intervals,
        regime_frequencies=dict(regime_frequencies),
        export_actions=export_count,
        hold_actions=sum(1 for action in actions if action == "HOLD"),
        average_spike_price=mean(spike_prices) if spike_prices else 0.0,
        highest_observed_price=max(prices) if prices else 0.0,
        total_simulated_cashflow=sum(cashflows),
        average_soc=mean(soc_values) if soc_values else 0.0,
        minimum_soc_reached=min_soc,
        longest_spike_cluster=_longest_spike_cluster(rows),
        percentage_exports_during_price_spike=export_spike_percentage,
        exports_concentrated_in_spike_regimes=(
            export_count > 0 and export_spike_percentage >= 80.0
        ),
        soc_exhaustion_occurred=(
            min_soc <= config.MIN_SOC_PERCENT if soc_values else False
        ),
        normal_period_activity_count=len(normal_activity_rows),
        normal_period_cashflow=normal_cashflow,
        normal_periods_generated_meaningful_activity=(
            len(normal_activity_rows) > 0 or abs(normal_cashflow) >= 0.01
        ),
    )


def write_markdown_report(
    summary: LiveObservationSummary,
    output_path: Path | str = LIVE_SUMMARY_OUTPUT,
) -> None:
    """Write a markdown report for a live observation summary."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(summary))


def render_terminal_summary(summary: LiveObservationSummary) -> str:
    """Render a human-readable terminal summary."""
    lines = [
        "LIVE OBSERVATION SUMMARY",
        "=" * 60,
        f"Total intervals observed: {summary.total_intervals_observed}",
        "Regime frequencies:",
    ]
    lines.extend(
        f"  - {regime}: {count} ({_percentage(count, summary.total_intervals_observed):.1f}%)"
        for regime, count in sorted(summary.regime_frequencies.items())
    )
    lines.extend(
        [
            f"EXPORT actions: {summary.export_actions}",
            f"HOLD actions: {summary.hold_actions}",
            f"Average spike price: ${summary.average_spike_price:.4f}/kWh",
            f"Highest observed price: ${summary.highest_observed_price:.4f}/kWh",
            f"Total simulated cashflow: ${summary.total_simulated_cashflow:.4f}",
            f"Average SoC: {summary.average_soc:.2f}%",
            f"Minimum SoC reached: {summary.minimum_soc_reached:.2f}%",
            f"Longest spike cluster: {summary.longest_spike_cluster} intervals",
            (
                "Exports during price_spike: "
                f"{summary.percentage_exports_during_price_spike:.1f}%"
            ),
            "",
            "Findings:",
            f"- {_format_concentration_finding(summary)}",
            f"- {_format_soc_finding(summary)}",
            f"- {_format_normal_activity_finding(summary)}",
        ]
    )
    return "\n".join(lines)


def render_markdown_report(summary: LiveObservationSummary) -> str:
    """Render the markdown report body."""
    regime_rows = "\n".join(
        "| {regime} | {count} | {pct:.1f}% |".format(
            regime=regime,
            count=count,
            pct=_percentage(count, summary.total_intervals_observed),
        )
        for regime, count in sorted(summary.regime_frequencies.items())
    )
    if not regime_rows:
        regime_rows = "| none | 0 | 0.0% |"

    return "\n".join(
        [
            "# Live Observation Summary",
            "",
            "Analytical report generated from `outputs/live_observation.csv`.",
            "",
            "## Summary Statistics",
            "",
            f"- Total intervals observed: {summary.total_intervals_observed}",
            f"- EXPORT actions: {summary.export_actions}",
            f"- HOLD actions: {summary.hold_actions}",
            f"- Average spike price: ${summary.average_spike_price:.4f}/kWh",
            f"- Highest observed price: ${summary.highest_observed_price:.4f}/kWh",
            f"- Total simulated cashflow: ${summary.total_simulated_cashflow:.4f}",
            f"- Average SoC: {summary.average_soc:.2f}%",
            f"- Minimum SoC reached: {summary.minimum_soc_reached:.2f}%",
            f"- Longest spike cluster: {summary.longest_spike_cluster} intervals",
            (
                "- Percentage of exports occurring during price_spike: "
                f"{summary.percentage_exports_during_price_spike:.1f}%"
            ),
            "",
            "## Regime Frequencies",
            "",
            "| Regime | Count | Share |",
            "| --- | ---: | ---: |",
            regime_rows,
            "",
            "## Findings",
            "",
            f"- {_format_concentration_finding(summary)}",
            f"- {_format_soc_finding(summary)}",
            f"- {_format_normal_activity_finding(summary)}",
            "",
        ]
    )


def run_live_summary(
    input_path: Path | str = LIVE_OBSERVATION_INPUT,
    output_path: Path | str = LIVE_SUMMARY_OUTPUT,
) -> LiveObservationSummary:
    """Load live observations, print terminal summary, and write markdown."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Live observation file not found: {input_path}")

    rows = load_live_observations(input_path)
    summary = summarise_live_observations(rows)
    print(render_terminal_summary(summary))
    write_markdown_report(summary, output_path)
    print(f"\nMarkdown report saved to: {output_path}")
    return summary


def _longest_spike_cluster(rows: List[Dict[str, str]]) -> int:
    longest = 0
    current = 0
    for row in rows:
        if _text(row, "regime") == PRICE_SPIKE:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _format_concentration_finding(summary: LiveObservationSummary) -> str:
    if summary.export_actions == 0:
        return "No EXPORT actions were observed, so export concentration cannot be assessed."
    if summary.exports_concentrated_in_spike_regimes:
        return (
            "Exports remained concentrated in spike regimes "
            f"({summary.percentage_exports_during_price_spike:.1f}% during price_spike)."
        )
    return (
        "Exports were not concentrated in spike regimes "
        f"({summary.percentage_exports_during_price_spike:.1f}% during price_spike)."
    )


def _format_soc_finding(summary: LiveObservationSummary) -> str:
    if summary.soc_exhaustion_occurred:
        return (
            "SoC exhaustion occurred: minimum simulated SoC reached "
            f"{summary.minimum_soc_reached:.2f}%."
        )
    return (
        "SoC exhaustion did not occur: minimum simulated SoC stayed at "
        f"{summary.minimum_soc_reached:.2f}%."
    )


def _format_normal_activity_finding(summary: LiveObservationSummary) -> str:
    if summary.normal_periods_generated_meaningful_activity:
        return (
            "Normal periods generated activity "
            f"({summary.normal_period_activity_count} active intervals, "
            f"${summary.normal_period_cashflow:.4f} simulated cashflow)."
        )
    return (
        "Normal periods did not generate meaningful activity "
        f"({summary.normal_period_activity_count} active intervals, "
        f"${summary.normal_period_cashflow:.4f} simulated cashflow)."
    )


def _percentage(count: int, total: int) -> float:
    return count / total * 100.0 if total else 0.0


def _number(row: Dict[str, str], field: str) -> float:
    value = row.get(field, "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text(row: Dict[str, str], field: str) -> str:
    return row.get(field, "").strip()
