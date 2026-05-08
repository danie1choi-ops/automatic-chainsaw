"""Run profitability attribution by price regime.

This script is a reproducible research runner. It loads historical price data,
existing battery backtest results, classifies price regimes, and attributes
realised profitability, cycles, export activity, and degradation by regime.

It does not implement strategy optimisation or new dispatch logic.
"""

import argparse
import csv
import html
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import config
from src.regime_analysis import REGIMES, RegimeAnalysisConfig, summarise_regimes
from src.regime_profitability_analysis import (
    RegimeProfitabilityConfig,
    cycles_by_regime,
    degradation_by_regime,
    export_activity_by_regime,
    profitability_by_regime,
)
from src.timestamp_alignment import (
    TimestampAlignmentConfig,
    align_market_prices,
    parse_timestamp,
    timestamp_alignment_report,
)


DEFAULT_PRICE_PATH = REPO_ROOT / "data" / "qld_prices_6m.csv"
DEFAULT_BACKTEST_PATH = REPO_ROOT / "outputs" / "backtest_results.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "research" / "output"
GENERATED_OUTPUT_FILES = (
    "timestamp_alignment_report.md",
    "timestamp_alignment_diagnostics.csv",
    "regime_classifications.csv",
    "profitability_by_regime.csv",
    "cycles_by_regime.csv",
    "export_activity_by_regime.csv",
    "degradation_by_regime.csv",
    "cumulative_pnl_by_regime.csv",
    "regime_study_report.md",
    "profit_contribution_by_regime.svg",
    "duration_vs_profitability.svg",
    "degradation_vs_revenue.svg",
    "cumulative_pnl_by_regime.svg",
)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_study_outputs(output_dir)

    price_rows = load_csv_rows(Path(args.prices))
    backtest_rows = load_csv_rows(Path(args.backtest))
    alignment_config = TimestampAlignmentConfig(
        interval_minutes=int(args.interval_minutes),
        timezone_name=args.timezone,
        rounding=args.timestamp_rounding,
        min_match_ratio=args.min_match_ratio,
    )
    alignment_diagnostics = timestamp_alignment_report(price_rows, backtest_rows, alignment_config)
    write_alignment_report(output_dir / "timestamp_alignment_report.md", alignment_diagnostics)
    write_alignment_diagnostics(output_dir / "timestamp_alignment_diagnostics.csv", alignment_diagnostics)
    try:
        dispatch_rows, alignment_note = prepare_dispatch_rows(
            price_rows,
            backtest_rows,
            alignment_config,
            alignment_diagnostics,
        )
    except ValueError as exc:
        write_alignment_failure_report(
            output_dir / "regime_study_report.md",
            args,
            alignment_diagnostics,
            str(exc),
        )
        print(f"Regime study stopped: {exc}", file=sys.stderr)
        print(f"Alignment diagnostics written to {output_dir}", file=sys.stderr)
        sys.exit(1)

    regime_config = RegimeAnalysisConfig(
        high_price_percentile=args.high_price_percentile,
        spike_price_percentile=args.spike_price_percentile,
        volatility_percentile=args.volatility_percentile,
        rolling_window_intervals=args.rolling_window_intervals,
        sustained_high_intervals=args.sustained_high_intervals,
        interval_hours=args.interval_minutes / 60.0,
        high_price_threshold=args.high_price_threshold,
        spike_price_threshold=args.spike_price_threshold,
        volatility_threshold=args.volatility_threshold,
    )
    profitability_config = RegimeProfitabilityConfig(
        battery_capacity_energy=config.BATTERY_CAPACITY_KWH,
        degradation_cost_per_energy=config.DEGRADATION_COST_PER_KWH,
        price_field="regime_price",
    )

    regime_summary = summarise_regimes(
        dispatch_rows,
        regime_config,
        price_field="regime_price",
    )
    regime_intervals = regime_summary["classified_intervals"]
    profitability = profitability_by_regime(
        dispatch_rows,
        regime_intervals,
        profitability_config=profitability_config,
    )
    cycles = cycles_by_regime(
        dispatch_rows,
        regime_intervals,
        profitability_config=profitability_config,
    )
    exports = export_activity_by_regime(
        dispatch_rows,
        regime_intervals,
        profitability_config=profitability_config,
    )
    degradation = degradation_by_regime(
        dispatch_rows,
        regime_intervals,
        profitability_config=profitability_config,
    )

    enriched_rows = enrich_rows(dispatch_rows, regime_intervals)
    cumulative_rows = cumulative_pnl_by_regime(enriched_rows)

    write_regime_classifications(output_dir / "regime_classifications.csv", enriched_rows)
    write_profitability_summary(output_dir / "profitability_by_regime.csv", profitability)
    write_cycles_summary(output_dir / "cycles_by_regime.csv", cycles)
    write_export_summary(output_dir / "export_activity_by_regime.csv", exports)
    write_degradation_summary(output_dir / "degradation_by_regime.csv", degradation)
    write_cumulative_pnl(output_dir / "cumulative_pnl_by_regime.csv", cumulative_rows)

    chart_paths = create_charts(output_dir, profitability, regime_summary, cumulative_rows)
    findings = build_findings(profitability, regime_summary)
    write_report(
        output_dir / "regime_study_report.md",
        args,
        alignment_note,
        regime_summary,
        profitability,
        findings,
        chart_paths,
    )

    print(f"Regime study complete. Outputs written to {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a historical NEM regime profitability study.")
    parser.add_argument("--prices", default=str(DEFAULT_PRICE_PATH), help="Historical price CSV path.")
    parser.add_argument("--backtest", default=str(DEFAULT_BACKTEST_PATH), help="Backtest result CSV path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--high-price-percentile", type=float, default=0.90)
    parser.add_argument("--spike-price-percentile", type=float, default=0.98)
    parser.add_argument("--volatility-percentile", type=float, default=0.90)
    parser.add_argument(
        "--high-price-threshold",
        type=float,
        default=config.EXPORT_PRICE_THRESHOLD,
        help="Fixed high-price threshold in the same unit as input prices.",
    )
    parser.add_argument(
        "--spike-price-threshold",
        type=float,
        default=config.EXPORT_PRICE_THRESHOLD * 2,
        help="Fixed spike threshold in the same unit as input prices.",
    )
    parser.add_argument(
        "--volatility-threshold",
        type=float,
        default=None,
        help="Optional fixed rolling-volatility threshold.",
    )
    parser.add_argument("--rolling-window-intervals", type=int, default=12)
    parser.add_argument("--sustained-high-intervals", type=int, default=6)
    parser.add_argument("--interval-minutes", type=float, default=float(config.INTERVAL_MINUTES))
    parser.add_argument("--timezone", default="Australia/Brisbane")
    parser.add_argument("--timestamp-rounding", choices=["nearest", "floor", "ceil"], default="nearest")
    parser.add_argument(
        "--min-match-ratio",
        type=float,
        default=1.0,
        help="Minimum required timestamp match ratio before regime attribution runs.",
    )
    return parser.parse_args()


def clear_previous_study_outputs(output_dir: Path) -> None:
    for file_name in GENERATED_OUTPUT_FILES:
        path = output_dir / file_name
        if path.exists():
            path.unlink()


def load_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    with path.open("r", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError(f"CSV contains no rows: {path}")

    return [normalise_row(row) for row in rows]


def normalise_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalised: Dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            normalised[key] = value
            continue
        stripped = value.strip() if isinstance(value, str) else value
        normalised[key] = parse_value(stripped)
    return normalised


def parse_value(value: Any) -> Any:
    if value == "":
        return None
    if isinstance(value, str):
        timestamp = parse_timestamp(value)
        if timestamp is not None:
            return timestamp
        try:
            return float(value)
        except ValueError:
            return value
    return value


def prepare_dispatch_rows(
    price_rows: Sequence[Dict[str, Any]],
    backtest_rows: Sequence[Dict[str, Any]],
    alignment_config: TimestampAlignmentConfig,
    alignment_diagnostics: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], str]:
    aligned_rows, _ = align_market_prices(
        price_rows,
        backtest_rows,
        alignment_config,
        price_field="price_per_kwh",
    )

    dispatch_rows: List[Dict[str, Any]] = []
    for row in aligned_rows:
        dispatch_row = dict(row)
        dispatch_row["cashflow"] = get_float(dispatch_row, "cashflow", default=0.0)
        dispatch_row["energy_kwh"] = get_float(dispatch_row, "energy_kwh", default=0.0)
        dispatch_row["degradation_cost"] = abs(dispatch_row["energy_kwh"]) * config.DEGRADATION_COST_PER_KWH
        dispatch_rows.append(dispatch_row)

    note = (
        f"Backtest rows were aligned to historical market prices by standardised timestamp. "
        f"Matched {alignment_diagnostics['matched_rows']} of "
        f"{alignment_diagnostics['total_backtest_rows']} rows "
        f"({alignment_diagnostics['matched_percent']:.2f}%). "
        "Regime attribution used aligned market prices only."
    )
    return dispatch_rows, note


def get_price(row: Dict[str, Any]) -> float:
    for field in ("price_per_kwh", "price_per_mwh", "RRP", "rrp", "price"):
        if field in row and row[field] is not None:
            return float(row[field])
    raise ValueError("row does not contain a recognised price field")


def get_float(row: Dict[str, Any], field: str, default: float = 0.0) -> float:
    value = row.get(field, default)
    if value is None:
        return default
    return float(value)


def enrich_rows(
    rows: Sequence[Dict[str, Any]],
    regime_intervals: Sequence[Any],
) -> List[Dict[str, Any]]:
    enriched = []
    for row, interval in zip(rows, regime_intervals):
        item = dict(row)
        item["regime"] = interval.regime
        item["rolling_volatility"] = interval.rolling_volatility
        item["consecutive_high_intervals"] = interval.consecutive_high_intervals
        item["profit"] = get_float(item, "cashflow", default=0.0)
        item["exported_energy"] = abs(get_float(item, "energy_kwh", default=0.0)) if get_float(item, "energy_kwh", default=0.0) < 0 else 0.0
        item["charged_energy"] = get_float(item, "energy_kwh", default=0.0) if get_float(item, "energy_kwh", default=0.0) > 0 else 0.0
        enriched.append(item)
    return enriched


def cumulative_pnl_by_regime(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    totals = {regime: 0.0 for regime in REGIMES}
    cumulative_rows = []
    for index, row in enumerate(rows):
        regime = row["regime"]
        totals[regime] += get_float(row, "profit", default=0.0)
        output_row = {
            "index": index,
            "timestamp": format_value(row.get("timestamp")),
            "regime": regime,
        }
        output_row.update(totals)
        cumulative_rows.append(output_row)
    return cumulative_rows


def write_regime_classifications(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    fields = [
        "timestamp",
        "regime_price",
        "regime",
        "rolling_volatility",
        "consecutive_high_intervals",
        "action",
        "energy_kwh",
        "cashflow",
        "degradation_cost",
    ]
    write_dict_rows(path, rows, fields)


def write_alignment_report(path: Path, report: Dict[str, Any]) -> None:
    lines = [
        "# Timestamp Alignment Report",
        "",
        "## Summary",
        "",
        f"- Price rows: {report['total_price_rows']}",
        f"- Backtest rows: {report['total_backtest_rows']}",
        f"- Matched rows: {report['matched_rows']}",
        f"- Matched intervals: {report['matched_percent']:.2f}%",
        f"- Missing market intervals: {report['missing_interval_count']}",
        f"- Duplicate market timestamps: {len(report['duplicate_price_timestamps'])}",
        f"- Duplicate backtest timestamps: {len(report['duplicate_backtest_timestamps'])}",
        "",
        "## Time Ranges",
        "",
        f"- Market price range: `{report['price_start']}` to `{report['price_end']}`",
        f"- Backtest range: `{report['backtest_start']}` to `{report['backtest_end']}`",
        "",
        "## Standardisation",
        "",
        f"- Timezone: `{report['config']['timezone_name']}`",
        f"- Interval minutes: `{report['config']['interval_minutes']}`",
        f"- Rounding: `{report['config']['rounding']}`",
        f"- Minimum match ratio: `{report['config']['min_match_ratio']:.2%}`",
        "",
        "## Unmatched Backtest Timestamp Sample",
        "",
    ]
    lines.extend(f"- `{timestamp}`" for timestamp in report["unmatched_backtest_timestamps"])
    if not report["unmatched_backtest_timestamps"]:
        lines.append("- None")
    lines.extend([
        "",
        "## Missing Market Interval Sample",
        "",
    ])
    lines.extend(f"- `{timestamp}`" for timestamp in report["missing_market_intervals"])
    if not report["missing_market_intervals"]:
        lines.append("- None")
    lines.extend([
        "",
        "## Duplicate Timestamp Diagnostics",
        "",
        f"- Market duplicate timestamps: `{report['duplicate_price_timestamps']}`",
        f"- Backtest duplicate timestamps: `{report['duplicate_backtest_timestamps']}`",
    ])
    path.write_text("\n".join(lines))


def write_alignment_diagnostics(path: Path, report: Dict[str, Any]) -> None:
    rows = [
        {"metric": "total_price_rows", "value": report["total_price_rows"]},
        {"metric": "total_backtest_rows", "value": report["total_backtest_rows"]},
        {"metric": "matched_rows", "value": report["matched_rows"]},
        {"metric": "matched_percent", "value": report["matched_percent"]},
        {"metric": "missing_interval_count", "value": report["missing_interval_count"]},
        {"metric": "unused_market_interval_count", "value": report["unused_market_interval_count"]},
        {"metric": "duplicate_price_timestamp_count", "value": len(report["duplicate_price_timestamps"])},
        {"metric": "duplicate_backtest_timestamp_count", "value": len(report["duplicate_backtest_timestamps"])},
        {"metric": "price_start", "value": report["price_start"]},
        {"metric": "price_end", "value": report["price_end"]},
        {"metric": "backtest_start", "value": report["backtest_start"]},
        {"metric": "backtest_end", "value": report["backtest_end"]},
    ]
    write_dict_rows(path, rows, ["metric", "value"])


def write_profitability_summary(path: Path, profitability: Dict[str, Any]) -> None:
    fields = [
        "regime",
        "interval_count",
        "average_profit",
        "total_profit",
        "average_spread_captured",
        "energy_exported",
        "export_interval_count",
        "cycle_contribution",
        "degradation_contribution",
        "profitability_share",
        "profitable",
        "degradation_dominates",
        "average_price",
    ]
    rows = [profitability["by_regime"][regime] for regime in REGIMES]
    write_dict_rows(path, rows, fields)


def write_cycles_summary(path: Path, cycles: Dict[str, float]) -> None:
    write_dict_rows(path, [{"regime": regime, "cycle_contribution": cycles[regime]} for regime in REGIMES], ["regime", "cycle_contribution"])


def write_export_summary(path: Path, exports: Dict[str, Dict[str, float]]) -> None:
    rows = [{"regime": regime, **exports[regime]} for regime in REGIMES]
    write_dict_rows(path, rows, ["regime", "energy_exported", "export_interval_count"])


def write_degradation_summary(path: Path, degradation: Dict[str, Dict[str, float]]) -> None:
    rows = [{"regime": regime, **degradation[regime]} for regime in REGIMES]
    write_dict_rows(path, rows, ["regime", "degradation_contribution", "degradation_dominates"])


def write_cumulative_pnl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    write_dict_rows(path, rows, ["index", "timestamp", "regime", *REGIMES])


def write_dict_rows(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: format_value(row.get(field)) for field in fields})


def create_charts(
    output_dir: Path,
    profitability: Dict[str, Any],
    regime_summary: Dict[str, Any],
    cumulative_rows: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    by_regime = profitability["by_regime"]
    profit_data = [(regime, by_regime[regime]["total_profit"]) for regime in REGIMES]
    duration_profit_data = [
        (
            regime,
            regime_summary["frequency"][regime]["share"],
            by_regime[regime]["profitability_share"],
        )
        for regime in REGIMES
    ]
    degradation_revenue_data = [
        (
            regime,
            by_regime[regime]["total_profit"],
            by_regime[regime]["degradation_contribution"],
        )
        for regime in REGIMES
    ]

    paths = {
        "profit_contribution": "profit_contribution_by_regime.svg",
        "duration_vs_profitability": "duration_vs_profitability.svg",
        "degradation_vs_revenue": "degradation_vs_revenue.svg",
        "cumulative_pnl": "cumulative_pnl_by_regime.svg",
    }
    write_bar_chart(output_dir / paths["profit_contribution"], profit_data, "Profit Contribution by Regime", "Profit")
    write_scatter_chart(output_dir / paths["duration_vs_profitability"], duration_profit_data, "Duration vs Profitability", "Interval Share", "Profit Share")
    write_grouped_bar_chart(output_dir / paths["degradation_vs_revenue"], degradation_revenue_data, "Degradation vs Revenue", "Profit", "Degradation")
    write_line_chart(output_dir / paths["cumulative_pnl"], cumulative_rows, "Cumulative P&L by Regime")
    return paths


def write_bar_chart(path: Path, data: Sequence[Tuple[str, float]], title: str, value_label: str) -> None:
    width, height = 900, 520
    margin = 80
    plot_height = height - 2 * margin
    plot_width = width - 2 * margin
    values = [value for _, value in data]
    min_value = min(0.0, min(values) if values else 0.0)
    max_value = max(0.0, max(values) if values else 0.0)
    span = max(max_value - min_value, 1.0)
    zero_y = margin + (max_value / span) * plot_height
    bar_width = plot_width / max(len(data), 1) * 0.65

    parts = svg_header(width, height, title)
    parts.append(axis_line(margin, zero_y, width - margin, zero_y))
    for index, (label, value) in enumerate(data):
        x = margin + index * (plot_width / len(data)) + (plot_width / len(data) - bar_width) / 2
        y = margin + ((max_value - max(value, 0.0)) / span) * plot_height
        if value < 0:
            y = zero_y
        bar_height = abs(value) / span * plot_height
        color = "#2f80ed" if value >= 0 else "#c0392b"
        parts.append(rect(x, y, bar_width, bar_height, color))
        parts.append(text(x + bar_width / 2, height - 35, label, 12, anchor="middle"))
        parts.append(text(x + bar_width / 2, y - 8 if value >= 0 else y + bar_height + 18, f"{value:.2f}", 12, anchor="middle"))
    parts.append(text(margin, 45, value_label, 12))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def write_scatter_chart(
    path: Path,
    data: Sequence[Tuple[str, float, float]],
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    width, height = 900, 520
    margin = 80
    parts = svg_header(width, height, title)
    parts.append(axis_line(margin, height - margin, width - margin, height - margin))
    parts.append(axis_line(margin, margin, margin, height - margin))
    max_x = max([x for _, x, _ in data] + [1.0])
    max_y = max([abs(y) for _, _, y in data] + [1.0])
    for label, x_value, y_value in data:
        x = margin + (x_value / max_x) * (width - 2 * margin)
        y = height - margin - (y_value / max_y) * (height - 2 * margin)
        parts.append(circle(x, y, 7, "#2f80ed"))
        parts.append(text(x + 10, y - 8, label, 12))
    parts.append(text(width / 2, height - 25, x_label, 13, anchor="middle"))
    parts.append(text(25, height / 2, y_label, 13))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def write_grouped_bar_chart(
    path: Path,
    data: Sequence[Tuple[str, float, float]],
    title: str,
    first_label: str,
    second_label: str,
) -> None:
    width, height = 940, 540
    margin = 80
    plot_width = width - 2 * margin
    plot_height = height - 2 * margin
    max_value = max([abs(v1) for _, v1, _ in data] + [abs(v2) for _, _, v2 in data] + [1.0])
    zero_y = height - margin
    group_width = plot_width / max(len(data), 1)
    bar_width = group_width * 0.28

    parts = svg_header(width, height, title)
    parts.append(axis_line(margin, zero_y, width - margin, zero_y))
    for index, (label, first, second) in enumerate(data):
        base_x = margin + index * group_width + group_width * 0.25
        first_height = abs(first) / max_value * plot_height
        second_height = abs(second) / max_value * plot_height
        parts.append(rect(base_x, zero_y - first_height if first >= 0 else zero_y, bar_width, first_height, "#2f80ed" if first >= 0 else "#c0392b"))
        parts.append(rect(base_x + bar_width + 6, zero_y - second_height, bar_width, second_height, "#f2a900"))
        parts.append(text(base_x + bar_width, height - 35, label, 12, anchor="middle"))
    parts.append(rect(width - 245, 35, 14, 14, "#2f80ed"))
    parts.append(text(width - 225, 47, first_label, 12))
    parts.append(rect(width - 145, 35, 14, 14, "#f2a900"))
    parts.append(text(width - 125, 47, second_label, 12))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def write_line_chart(path: Path, rows: Sequence[Dict[str, Any]], title: str) -> None:
    width, height = 960, 560
    margin = 80
    parts = svg_header(width, height, title)
    parts.append(axis_line(margin, height - margin, width - margin, height - margin))
    parts.append(axis_line(margin, margin, margin, height - margin))
    if not rows:
        parts.append(svg_footer())
        path.write_text("\n".join(parts))
        return

    values = [float(row[regime]) for row in rows for regime in REGIMES]
    min_value = min(values + [0.0])
    max_value = max(values + [0.0])
    span = max(max_value - min_value, 1.0)
    colors = {
        "normal": "#2f80ed",
        "volatile": "#8e44ad",
        "negative_pricing": "#27ae60",
        "price_spike": "#c0392b",
        "sustained_high_price_event": "#f2a900",
    }
    for regime in REGIMES:
        points = []
        for index, row in enumerate(rows):
            x = margin + (index / max(len(rows) - 1, 1)) * (width - 2 * margin)
            y = height - margin - ((float(row[regime]) - min_value) / span) * (height - 2 * margin)
            points.append(f"{x:.1f},{y:.1f}")
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[regime]}" stroke-width="2" />')
    for index, regime in enumerate(REGIMES):
        y = 35 + index * 20
        parts.append(rect(width - 280, y - 10, 12, 12, colors[regime]))
        parts.append(text(width - 262, y, regime, 12))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def build_findings(
    profitability: Dict[str, Any],
    regime_summary: Dict[str, Any],
) -> List[str]:
    by_regime = profitability["by_regime"]
    top_regime = profitability["top_pnl_regimes"][0] if profitability["top_pnl_regimes"] else None
    findings = []

    if top_regime is not None:
        top = by_regime[top_regime]
        findings.append(
            f"{top_regime} contributed the largest absolute P&L: {top['total_profit']:.2f} "
            f"({top['profitability_share']:.1%} of total profit)."
        )

    spike_share = by_regime["price_spike"]["profitability_share"]
    spike_duration = regime_summary["frequency"]["price_spike"]["share"]
    findings.append(
        f"Price spikes represented {spike_duration:.1%} of intervals and contributed {spike_share:.1%} of total profitability."
    )

    normal = by_regime["normal"]
    if normal["degradation_dominates"]:
        findings.append("In normal periods, degradation outweighed realised value.")
    else:
        findings.append("In normal periods, degradation did not outweigh realised value.")

    volatility_dependent_profit = (
        by_regime["volatile"]["total_profit"]
        + by_regime["price_spike"]["total_profit"]
        + by_regime["sustained_high_price_event"]["total_profit"]
    )
    total_profit = profitability["total_profit"]
    volatility_share = volatility_dependent_profit / total_profit if total_profit else 0.0
    findings.append(
        f"Volatility-linked regimes contributed {volatility_share:.1%} of total profitability."
    )
    return findings


def write_report(
    path: Path,
    args: argparse.Namespace,
    alignment_note: str,
    regime_summary: Dict[str, Any],
    profitability: Dict[str, Any],
    findings: Sequence[str],
    chart_paths: Dict[str, str],
) -> None:
    lines = [
        "# Regime Profitability Study",
        "",
        "## Inputs",
        "",
        f"- Prices: `{args.prices}`",
        f"- Backtest: `{args.backtest}`",
        f"- Alignment: {alignment_note}",
        "",
        "## Key Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in findings)
    lines.extend([
        "",
        "## Regime Summary",
        "",
        "| Regime | Interval Share | Total Profit | Profit Share | Energy Exported | Cycles | Degradation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for regime in REGIMES:
        stats = profitability["by_regime"][regime]
        frequency = regime_summary["frequency"][regime]
        lines.append(
            f"| `{regime}` | {frequency['share']:.2%} | {stats['total_profit']:.4f} | "
            f"{stats['profitability_share']:.2%} | {stats['energy_exported']:.4f} | "
            f"{stats['cycle_contribution']:.4f} | {stats['degradation_contribution']:.4f} |"
        )
    lines.extend([
        "",
        "## Charts",
        "",
        f"![Profit contribution by regime]({chart_paths['profit_contribution']})",
        "",
        f"![Duration vs profitability]({chart_paths['duration_vs_profitability']})",
        "",
        f"![Degradation vs revenue]({chart_paths['degradation_vs_revenue']})",
        "",
        f"![Cumulative P&L by regime]({chart_paths['cumulative_pnl']})",
        "",
        "## Reproducibility",
        "",
        "Run from the repository root:",
        "",
        "```bash",
        "python3 research/run_regime_study.py",
        "```",
        "",
        "This study is attribution-only and does not change dispatch decisions.",
    ])
    path.write_text("\n".join(lines))


def write_alignment_failure_report(
    path: Path,
    args: argparse.Namespace,
    report: Dict[str, Any],
    error: str,
) -> None:
    lines = [
        "# Regime Profitability Study",
        "",
        "## Status",
        "",
        "Timestamp alignment failed. Regime attribution was not run.",
        "",
        "## Inputs",
        "",
        f"- Prices: `{args.prices}`",
        f"- Backtest: `{args.backtest}`",
        "",
        "## Alignment Error",
        "",
        f"- {error}",
        "",
        "## Diagnostics",
        "",
        f"- Matched rows: {report['matched_rows']} of {report['total_backtest_rows']}",
        f"- Matched intervals: {report['matched_percent']:.2f}%",
        f"- Market price range: `{report['price_start']}` to `{report['price_end']}`",
        f"- Backtest range: `{report['backtest_start']}` to `{report['backtest_end']}`",
        f"- Missing market intervals: {report['missing_interval_count']}",
        f"- Duplicate market timestamps: {len(report['duplicate_price_timestamps'])}",
        f"- Duplicate backtest timestamps: {len(report['duplicate_backtest_timestamps'])}",
        "",
        "## Unmatched Backtest Timestamp Sample",
        "",
    ]
    lines.extend(f"- `{timestamp}`" for timestamp in report["unmatched_backtest_timestamps"])
    if not report["unmatched_backtest_timestamps"]:
        lines.append("- None")
    lines.extend([
        "",
        "Regime analysis uses aligned historical market prices only. Regenerate or provide backtest results for the same interval range as the selected price file.",
    ])
    path.write_text("\n".join(lines))


def format_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.10g}"
    return value


def svg_header(width: int, height: int, title: str) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
        text(width / 2, 28, title, 18, anchor="middle", weight="700"),
    ]


def svg_footer() -> str:
    return "</svg>"


def rect(x: float, y: float, width: float, height: float, fill: str) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{fill}" />'


def circle(x: float, y: float, radius: float, fill: str) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}" />'


def axis_line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#333333" stroke-width="1" />'


def text(
    x: float,
    y: float,
    content: Any,
    size: int,
    anchor: str = "start",
    weight: str = "400",
) -> str:
    escaped = html.escape(str(content))
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="#222222">{escaped}</text>'
    )


if __name__ == "__main__":
    main()
