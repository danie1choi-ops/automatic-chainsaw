"""Run an analytical battery saturation study from regime attribution outputs."""

import argparse
import csv
import html
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import config
from src.regime_analysis import (
    NEGATIVE_PRICING,
    NORMAL,
    PRICE_SPIKE,
    REGIMES,
    SUSTAINED_HIGH_PRICE_EVENT,
    VOLATILE,
)
from src.saturation_simulator import (
    SaturationConfig,
    compare_participation_levels,
)


DEFAULT_INPUT = REPO_ROOT / "research" / "output" / "regime_classifications.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "research" / "output" / "saturation"
PARTICIPATION_LEVELS = (1, 10, 100, 1000, 10000)
GENERATED_OUTPUT_FILES = (
    "saturation_profit_curve.csv",
    "saturation_regime_profitability.csv",
    "saturation_regime_frequencies.csv",
    "saturation_assumptions.csv",
    "saturation_study_report.md",
    "profit_vs_participation.svg",
    "spike_profitability_decay.svg",
    "regime_contribution_changes.svg",
    "volatility_compression.svg",
)


def main() -> None:
    args = parse_args()
    input_path = Path(args.regime_classifications)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_outputs(output_dir)

    rows = load_regime_rows(input_path)
    base_config = SaturationConfig(
        battery_size=args.battery_size,
        reaction_aggressiveness=args.reaction_aggressiveness,
        spread_compression_factor=args.spread_compression_factor,
        export_window_competition_factor=args.export_window_competition_factor,
        degradation_cost_per_energy=args.degradation_cost_per_energy,
    )
    comparison = compare_participation_levels(
        rows,
        PARTICIPATION_LEVELS,
        base_config,
    )
    curve = enrich_profit_curve(comparison["profit_decay_curve"])
    regime_rows = flatten_regime_profitability(comparison["scenario_results"])
    frequencies = regime_frequencies(rows)
    findings = build_findings(curve, regime_rows)

    write_dict_rows(output_dir / "saturation_profit_curve.csv", curve, [
        "number_batteries",
        "single_battery_profit",
        "per_battery_profit",
        "fleet_profit",
        "profit_decay",
        "fleet_profit_decay",
        "volatility_compression",
        "export_window_competition",
        "per_battery_degradation",
        "degradation_to_profit_ratio",
    ])
    write_dict_rows(output_dir / "saturation_regime_profitability.csv", regime_rows, [
        "number_batteries",
        "regime",
        "interval_count",
        "total_profit",
        "average_profit",
        "profitability_share",
        "energy_exported",
        "cycle_contribution",
        "degradation_contribution",
        "degradation_dominates",
    ])
    write_dict_rows(output_dir / "saturation_regime_frequencies.csv", frequencies, [
        "regime",
        "interval_count",
        "interval_share",
    ])
    write_assumptions(output_dir / "saturation_assumptions.csv", args, base_config)

    chart_paths = create_charts(output_dir, curve, regime_rows)
    write_report(
        output_dir / "saturation_study_report.md",
        args,
        input_path,
        curve,
        regime_rows,
        frequencies,
        findings,
        chart_paths,
    )

    print(f"Saturation study complete. Outputs written to {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run battery saturation sensitivity study.")
    parser.add_argument(
        "--regime-classifications",
        default=str(DEFAULT_INPUT),
        help="CSV from research/output/regime_classifications.csv.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--battery-size", type=float, default=config.BATTERY_CAPACITY_KWH)
    parser.add_argument("--reaction-aggressiveness", type=float, default=1.0)
    parser.add_argument("--spread-compression-factor", type=float, default=0.05)
    parser.add_argument("--export-window-competition-factor", type=float, default=0.02)
    parser.add_argument("--degradation-cost-per-energy", type=float, default=config.DEGRADATION_COST_PER_KWH)
    return parser.parse_args()


def clear_previous_outputs(output_dir: Path) -> None:
    for file_name in GENERATED_OUTPUT_FILES:
        path = output_dir / file_name
        if path.exists():
            path.unlink()


def load_regime_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Regime classification CSV not found: {path}. Run research/run_regime_study.py first."
        )
    with path.open("r", newline="") as handle:
        rows = [normalise_row(row) for row in csv.DictReader(handle)]
    if not rows:
        raise ValueError(f"Regime classification CSV contains no rows: {path}")
    missing_regime = [index for index, row in enumerate(rows) if not row.get("regime")]
    if missing_regime:
        raise ValueError(f"Rows missing regime labels: {missing_regime[:10]}")
    return rows


def normalise_row(row: Dict[str, str]) -> Dict[str, Any]:
    normalised: Dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            normalised[key] = value
            continue
        text = value.strip()
        if text == "":
            normalised[key] = None
            continue
        try:
            normalised[key] = float(text)
        except ValueError:
            normalised[key] = text

    if "regime_price" in normalised:
        normalised["price"] = normalised["regime_price"]
    if "cashflow" in normalised:
        normalised["profit"] = normalised["cashflow"]
    return normalised


def enrich_profit_curve(curve: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for point in curve:
        baseline_fleet_profit = point["single_battery_profit"] * point["number_batteries"]
        fleet_profit_decay = (
            1.0 - point["fleet_profit"] / baseline_fleet_profit
            if baseline_fleet_profit
            else 0.0
        )
        degradation_to_profit_ratio = (
            point["per_battery_degradation"] / point["per_battery_profit"]
            if point["per_battery_profit"] > 0
            else 0.0
        )
        enriched.append({
            **point,
            "fleet_profit_decay": fleet_profit_decay,
            "degradation_to_profit_ratio": degradation_to_profit_ratio,
        })
    return enriched


def flatten_regime_profitability(scenario_results: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for number_batteries in sorted(scenario_results):
        by_regime = scenario_results[number_batteries]["regime_profitability"]["by_regime"]
        for regime in REGIMES:
            stats = by_regime[regime]
            rows.append({
                "number_batteries": number_batteries,
                "regime": regime,
                "interval_count": stats["interval_count"],
                "total_profit": stats["total_profit"],
                "average_profit": stats["average_profit"],
                "profitability_share": stats["profitability_share"],
                "energy_exported": stats["energy_exported"],
                "cycle_contribution": stats["cycle_contribution"],
                "degradation_contribution": stats["degradation_contribution"],
                "degradation_dominates": stats["degradation_dominates"],
            })
    return rows


def regime_frequencies(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts = {regime: 0 for regime in REGIMES}
    for row in rows:
        counts[row["regime"]] = counts.get(row["regime"], 0) + 1
    total = len(rows)
    return [
        {
            "regime": regime,
            "interval_count": counts.get(regime, 0),
            "interval_share": counts.get(regime, 0) / total if total else 0.0,
        }
        for regime in REGIMES
    ]


def build_findings(
    curve: Sequence[Dict[str, Any]],
    regime_rows: Sequence[Dict[str, Any]],
) -> List[str]:
    collapse_point = first_material_collapse(curve)
    highest = curve[-1]
    spike_rows = [row for row in regime_rows if row["regime"] == PRICE_SPIKE]
    initial_spike = next(row for row in spike_rows if row["number_batteries"] == 1)
    final_spike = next(row for row in spike_rows if row["number_batteries"] == highest["number_batteries"])
    final_rows = [row for row in regime_rows if row["number_batteries"] == highest["number_batteries"]]
    degradation_dominated = [row["regime"] for row in final_rows if row["degradation_dominates"]]

    if collapse_point:
        collapse_text = (
            f"Per-battery profitability materially collapses by {collapse_point['number_batteries']} batteries "
            f"({collapse_point['profit_decay']:.1%} decay)."
        )
    else:
        collapse_text = "Per-battery profitability does not reach the 50% decay threshold in the simulated range."

    spike_decay = (
        1.0 - final_spike["total_profit"] / initial_spike["total_profit"]
        if initial_spike["total_profit"]
        else 0.0
    )
    spike_text = (
        f"Spike profitability changes from {initial_spike['total_profit']:.2f} to "
        f"{final_spike['total_profit']:.2f} by {highest['number_batteries']} batteries "
        f"({spike_decay:.1%} decay)."
    )
    degradation_text = (
        "At the highest participation level, degradation dominates: "
        + ", ".join(degradation_dominated)
        if degradation_dominated
        else "At the highest participation level, no regime is degradation-dominated."
    )
    implication_text = (
        "Residential systems are most exposed to per-battery revenue compression in shared spike windows; "
        "grid-scale systems may preserve fleet revenue longer but still face spread compression and degradation drag."
    )

    return [collapse_text, spike_text, degradation_text, implication_text]


def first_material_collapse(curve: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    for point in curve:
        if point["profit_decay"] >= 0.50:
            return point
    return {}


def create_charts(
    output_dir: Path,
    curve: Sequence[Dict[str, Any]],
    regime_rows: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    paths = {
        "profit_vs_participation": "profit_vs_participation.svg",
        "spike_profitability_decay": "spike_profitability_decay.svg",
        "regime_contribution_changes": "regime_contribution_changes.svg",
        "volatility_compression": "volatility_compression.svg",
    }
    write_multi_line_chart(
        output_dir / paths["profit_vs_participation"],
        curve,
        "Profit vs Participation",
        {
            "per_battery_profit": "#2f80ed",
            "fleet_profit": "#27ae60",
        },
    )
    spike_rows = [row for row in regime_rows if row["regime"] == PRICE_SPIKE]
    write_single_line_chart(
        output_dir / paths["spike_profitability_decay"],
        spike_rows,
        "Spike Profitability Decay",
        "total_profit",
        "#c0392b",
    )
    write_regime_contribution_chart(
        output_dir / paths["regime_contribution_changes"],
        regime_rows,
    )
    write_single_line_chart(
        output_dir / paths["volatility_compression"],
        curve,
        "Volatility Compression",
        "volatility_compression",
        "#8e44ad",
    )
    return paths


def write_multi_line_chart(
    path: Path,
    rows: Sequence[Dict[str, Any]],
    title: str,
    series: Dict[str, str],
) -> None:
    width, height = 980, 560
    margin = 80
    values = [float(row[field]) for row in rows for field in series]
    min_value = min(values + [0.0])
    max_value = max(values + [0.0])
    parts = svg_header(width, height, title)
    parts.extend(axis(width, height, margin))
    for field, color in series.items():
        parts.append(polyline(points_for(rows, field, width, height, margin, min_value, max_value), color))
    parts.extend(legend(series, width))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def write_single_line_chart(
    path: Path,
    rows: Sequence[Dict[str, Any]],
    title: str,
    field: str,
    color: str,
) -> None:
    width, height = 980, 560
    margin = 80
    values = [float(row[field]) for row in rows]
    min_value = min(values + [0.0])
    max_value = max(values + [0.0])
    parts = svg_header(width, height, title)
    parts.extend(axis(width, height, margin))
    parts.append(polyline(points_for(rows, field, width, height, margin, min_value, max_value), color))
    for row, point in zip(rows, points_for(rows, field, width, height, margin, min_value, max_value).split()):
        x, y = point.split(",")
        parts.append(text(float(x), float(y) - 8, str(int(row["number_batteries"])), 11, anchor="middle"))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def write_regime_contribution_chart(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    width, height = 1040, 600
    margin = 80
    values = [float(row["profitability_share"]) for row in rows]
    min_value = min(values + [0.0])
    max_value = max(values + [0.0])
    colors = {
        NORMAL: "#2f80ed",
        VOLATILE: "#8e44ad",
        NEGATIVE_PRICING: "#27ae60",
        PRICE_SPIKE: "#c0392b",
        SUSTAINED_HIGH_PRICE_EVENT: "#f2a900",
    }
    parts = svg_header(width, height, "Regime Contribution Changes")
    parts.extend(axis(width, height, margin))
    for regime in REGIMES:
        regime_rows = [row for row in rows if row["regime"] == regime]
        parts.append(polyline(
            points_for(regime_rows, "profitability_share", width, height, margin, min_value, max_value),
            colors[regime],
        ))
    parts.extend(legend(colors, width))
    parts.append(svg_footer())
    path.write_text("\n".join(parts))


def points_for(
    rows: Sequence[Dict[str, Any]],
    field: str,
    width: int,
    height: int,
    margin: int,
    min_value: float,
    max_value: float,
) -> str:
    if not rows:
        return ""
    span = max(max_value - min_value, 1.0)
    points = []
    for index, row in enumerate(rows):
        x = margin + (index / max(len(rows) - 1, 1)) * (width - 2 * margin)
        y = height - margin - ((float(row[field]) - min_value) / span) * (height - 2 * margin)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def write_report(
    path: Path,
    args: argparse.Namespace,
    input_path: Path,
    curve: Sequence[Dict[str, Any]],
    regime_rows: Sequence[Dict[str, Any]],
    frequencies: Sequence[Dict[str, Any]],
    findings: Sequence[str],
    chart_paths: Dict[str, str],
) -> None:
    lines = [
        "# Saturation Study",
        "",
        "## Inputs",
        "",
        f"- Regime classifications: `{input_path}`",
        f"- Participation levels: `{', '.join(str(level) for level in PARTICIPATION_LEVELS)}`",
        "",
        "## Assumptions",
        "",
        f"- Battery size: `{args.battery_size}`",
        f"- Reaction aggressiveness: `{args.reaction_aggressiveness}`",
        f"- Spread compression factor: `{args.spread_compression_factor}`",
        f"- Export-window competition factor: `{args.export_window_competition_factor}`",
        f"- Degradation cost per energy: `{args.degradation_cost_per_energy}`",
        "",
        "## Key Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in findings)
    lines.extend([
        "",
        "## Profit Decay Curve",
        "",
        "| Batteries | Per-Battery Profit | Fleet Profit | Profit Decay | Volatility Compression | Degradation |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for point in curve:
        lines.append(
            f"| {point['number_batteries']} | {point['per_battery_profit']:.4f} | "
            f"{point['fleet_profit']:.4f} | {point['profit_decay']:.2%} | "
            f"{point['volatility_compression']:.2%} | {point['per_battery_degradation']:.4f} |"
        )
    lines.extend([
        "",
        "## Historical Regime Frequencies",
        "",
        "| Regime | Interval Share | Interval Count |",
        "| --- | ---: | ---: |",
    ])
    for row in frequencies:
        lines.append(f"| `{row['regime']}` | {row['interval_share']:.2%} | {row['interval_count']} |")
    lines.extend([
        "",
        "## Charts",
        "",
        f"![Profit vs participation]({chart_paths['profit_vs_participation']})",
        "",
        f"![Spike profitability decay]({chart_paths['spike_profitability_decay']})",
        "",
        f"![Regime contribution changes]({chart_paths['regime_contribution_changes']})",
        "",
        f"![Volatility compression]({chart_paths['volatility_compression']})",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "python3 research/run_saturation_study.py",
        "```",
        "",
        "This study is analytical only. It does not change strategy logic or dispatch decisions.",
    ])
    path.write_text("\n".join(lines))


def write_assumptions(path: Path, args: argparse.Namespace, base_config: SaturationConfig) -> None:
    rows = [
        {"parameter": "participation_levels", "value": ",".join(str(level) for level in PARTICIPATION_LEVELS)},
        {"parameter": "battery_size", "value": args.battery_size},
        {"parameter": "reaction_aggressiveness", "value": base_config.reaction_aggressiveness},
        {"parameter": "spread_compression_factor", "value": base_config.spread_compression_factor},
        {"parameter": "export_window_competition_factor", "value": base_config.export_window_competition_factor},
        {"parameter": "degradation_cost_per_energy", "value": base_config.degradation_cost_per_energy},
        {"parameter": "affected_regimes", "value": ",".join(base_config.affected_regimes)},
    ]
    write_dict_rows(path, rows, ["parameter", "value"])


def write_dict_rows(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: format_value(row.get(field)) for field in fields})


def format_value(value: Any) -> Any:
    if isinstance(value, float):
        return f"{value:.10g}"
    return value


def svg_header(width: int, height: int, title: str) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
        text(width / 2, 30, title, 18, anchor="middle", weight="700"),
    ]


def svg_footer() -> str:
    return "</svg>"


def axis(width: int, height: int, margin: int) -> List[str]:
    return [
        f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#333333" />',
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#333333" />',
    ]


def polyline(points: str, color: str) -> str:
    return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" />'


def legend(series: Dict[str, str], width: int) -> List[str]:
    parts = []
    for index, (label, color) in enumerate(series.items()):
        y = 55 + index * 20
        parts.append(f'<rect x="{width - 310}" y="{y - 10}" width="12" height="12" fill="{color}" />')
        parts.append(text(width - 292, y, label, 12))
    return parts


def text(
    x: float,
    y: float,
    content: Any,
    size: int,
    anchor: str = "start",
    weight: str = "400",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="#222222">'
        f'{html.escape(str(content))}</text>'
    )


if __name__ == "__main__":
    main()
