"""Analytical saturation simulator for battery arbitrage participation.

The simulator applies explicit spread-compression assumptions to realised
dispatch/profit rows. It is not a market model and does not introduce dispatch
or strategy logic.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from src.regime_analysis import (
    PRICE_SPIKE,
    REGIMES,
    SUSTAINED_HIGH_PRICE_EVENT,
    VOLATILE,
)
from src.regime_profitability_analysis import (
    RegimeProfitabilityConfig,
    profitability_by_regime,
)


VOLATILITY_REGIMES = (VOLATILE, PRICE_SPIKE, SUSTAINED_HIGH_PRICE_EVENT)


@dataclass(frozen=True)
class SaturationConfig:
    """Configurable assumptions for saturation analysis."""

    number_batteries: int = 1
    battery_size: float = 13.5
    reaction_aggressiveness: float = 1.0
    spread_compression_factor: float = 0.05
    export_window_competition_factor: float = 0.02
    degradation_cost_per_energy: float = 0.0
    affected_regimes: Sequence[str] = field(default_factory=lambda: VOLATILITY_REGIMES)

    def validate(self) -> None:
        if self.number_batteries <= 0:
            raise ValueError("number_batteries must be greater than zero")
        if self.battery_size <= 0:
            raise ValueError("battery_size must be greater than zero")
        if self.reaction_aggressiveness < 0:
            raise ValueError("reaction_aggressiveness cannot be negative")
        if self.spread_compression_factor < 0:
            raise ValueError("spread_compression_factor cannot be negative")
        if self.export_window_competition_factor < 0:
            raise ValueError("export_window_competition_factor cannot be negative")
        if self.degradation_cost_per_energy < 0:
            raise ValueError("degradation_cost_per_energy cannot be negative")


def simulate_saturation(
    dispatch_results: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]] = None,
    config: Optional[SaturationConfig] = None,
) -> Dict[str, Any]:
    """Simulate one battery participation level against realised dispatch rows."""
    cfg = config or SaturationConfig()
    cfg.validate()
    rows = list(dispatch_results)
    if not rows:
        raise ValueError("dispatch_results must contain at least one row")

    regimes = _resolve_regimes(rows, regime_intervals)
    if len(regimes) != len(rows):
        raise ValueError("dispatch_results and regime_intervals must have the same length")

    adjusted_rows = []
    total_baseline_profit = 0.0
    total_adjusted_profit = 0.0
    total_baseline_degradation = 0.0
    total_adjusted_degradation = 0.0
    baseline_exported_energy = 0.0
    adjusted_exported_energy = 0.0
    compression_values = []

    for row, regime in zip(rows, regimes):
        adjusted = _adjust_row(row, regime, cfg)
        adjusted_rows.append(adjusted)
        total_baseline_profit += adjusted["baseline_profit"]
        total_adjusted_profit += adjusted["profit"]
        total_baseline_degradation += adjusted["baseline_degradation_cost"]
        total_adjusted_degradation += adjusted["degradation_cost"]
        baseline_exported_energy += adjusted["baseline_exported_energy"]
        adjusted_exported_energy += adjusted["exported_energy"]
        compression_values.append(adjusted["volatility_compression"])

    profitability_config = RegimeProfitabilityConfig(
        battery_capacity_energy=cfg.battery_size,
        degradation_cost_per_energy=cfg.degradation_cost_per_energy,
        price_field="price",
        profit_field="profit",
        degradation_field="degradation_cost",
        export_energy_field="exported_energy",
        charge_energy_field="charged_energy",
        spread_field="spread_captured",
    )
    regime_profitability = profitability_by_regime(
        adjusted_rows,
        regimes,
        profitability_config=profitability_config,
    )

    profit_decay = (
        1.0 - total_adjusted_profit / total_baseline_profit
        if total_baseline_profit
        else 0.0
    )
    export_window_competition = (
        1.0 - adjusted_exported_energy / baseline_exported_energy
        if baseline_exported_energy
        else 0.0
    )

    return {
        "number_batteries": cfg.number_batteries,
        "battery_size": cfg.battery_size,
        "single_battery_profit": total_baseline_profit,
        "per_battery_profit": total_adjusted_profit,
        "fleet_profit": total_adjusted_profit * cfg.number_batteries,
        "profit_decay": profit_decay,
        "volatility_compression": _average(compression_values),
        "export_window_competition": export_window_competition,
        "single_battery_degradation": total_baseline_degradation,
        "per_battery_degradation": total_adjusted_degradation,
        "fleet_degradation": total_adjusted_degradation * cfg.number_batteries,
        "regime_profitability": regime_profitability,
        "adjusted_rows": adjusted_rows,
        "assumptions": {
            "reaction_aggressiveness": cfg.reaction_aggressiveness,
            "spread_compression_factor": cfg.spread_compression_factor,
            "export_window_competition_factor": cfg.export_window_competition_factor,
            "affected_regimes": list(cfg.affected_regimes),
        },
    }


def compare_participation_levels(
    dispatch_results: Sequence[Any],
    participation_levels: Sequence[int],
    base_config: Optional[SaturationConfig] = None,
    regime_intervals: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Compare profitability decay over multiple participation levels."""
    if not participation_levels:
        raise ValueError("participation_levels must contain at least one level")

    cfg = base_config or SaturationConfig()
    curve = []
    scenario_results = {}
    for number_batteries in participation_levels:
        scenario_config = SaturationConfig(
            number_batteries=number_batteries,
            battery_size=cfg.battery_size,
            reaction_aggressiveness=cfg.reaction_aggressiveness,
            spread_compression_factor=cfg.spread_compression_factor,
            export_window_competition_factor=cfg.export_window_competition_factor,
            degradation_cost_per_energy=cfg.degradation_cost_per_energy,
            affected_regimes=cfg.affected_regimes,
        )
        result = simulate_saturation(dispatch_results, regime_intervals, scenario_config)
        scenario_results[number_batteries] = result
        curve.append({
            "number_batteries": number_batteries,
            "single_battery_profit": result["single_battery_profit"],
            "per_battery_profit": result["per_battery_profit"],
            "fleet_profit": result["fleet_profit"],
            "profit_decay": result["profit_decay"],
            "volatility_compression": result["volatility_compression"],
            "export_window_competition": result["export_window_competition"],
            "per_battery_degradation": result["per_battery_degradation"],
        })

    return {
        "profit_decay_curve": curve,
        "scenario_results": scenario_results,
        "most_saturated_case": scenario_results[max(participation_levels)],
    }


def profitability_decay_vs_participation(
    dispatch_results: Sequence[Any],
    participation_levels: Sequence[int],
    base_config: Optional[SaturationConfig] = None,
    regime_intervals: Optional[Sequence[Any]] = None,
) -> List[Dict[str, float]]:
    """Return only the profit decay curve for plotting or tabular output."""
    return compare_participation_levels(
        dispatch_results,
        participation_levels,
        base_config,
        regime_intervals,
    )["profit_decay_curve"]


def _adjust_row(row: Any, regime: str, config: SaturationConfig) -> Dict[str, Any]:
    source = dict(row) if isinstance(row, dict) else vars(row).copy()
    profit = _extract_float(source, ["profit", "cashflow", "net_cashflow"], 0.0)
    degradation = _extract_float(source, ["degradation_cost", "degradation"], None)
    exported_energy = _extract_exported_energy(source)
    charged_energy = _extract_charged_energy(source)
    throughput = exported_energy + charged_energy
    if degradation is None:
        degradation = throughput * config.degradation_cost_per_energy

    gross_value = profit + degradation
    spread = _extract_float(source, ["spread_captured", "captured_spread", "arbitrage_spread"], None)
    price = _extract_float(source, ["price", "price_per_kwh", "price_per_mwh", "regime_price"], 0.0)

    compression = _participation_compression(config, regime)
    competition = _export_competition(config, regime)
    adjusted_exported_energy = exported_energy * competition
    adjusted_charged_energy = charged_energy * competition if regime in config.affected_regimes else charged_energy
    adjusted_degradation = degradation * (
        (adjusted_exported_energy + adjusted_charged_energy) / throughput
        if throughput
        else 1.0
    )

    if regime in config.affected_regimes and gross_value > 0:
        adjusted_gross_value = gross_value * (1.0 - compression) * competition
    else:
        adjusted_gross_value = gross_value

    adjusted_profit = adjusted_gross_value - adjusted_degradation
    adjusted_spread = spread * (1.0 - compression) if spread is not None else None

    adjusted = dict(source)
    adjusted.update({
        "regime": regime,
        "price": price,
        "baseline_profit": profit,
        "profit": adjusted_profit,
        "baseline_degradation_cost": degradation,
        "degradation_cost": adjusted_degradation,
        "baseline_exported_energy": exported_energy,
        "exported_energy": adjusted_exported_energy,
        "charged_energy": adjusted_charged_energy,
        "spread_captured": adjusted_spread,
        "spread_capture_multiplier": 1.0 - compression,
        "export_window_multiplier": competition,
        "volatility_compression": compression,
    })
    return adjusted


def _participation_compression(config: SaturationConfig, regime: str) -> float:
    if regime not in config.affected_regimes:
        return 0.0
    pressure = max(config.number_batteries - 1, 0) * config.reaction_aggressiveness
    compression = pressure * config.spread_compression_factor
    return min(max(compression, 0.0), 0.95)


def _export_competition(config: SaturationConfig, regime: str) -> float:
    if regime not in config.affected_regimes:
        return 1.0
    pressure = max(config.number_batteries - 1, 0) * config.reaction_aggressiveness
    multiplier = 1.0 / (1.0 + pressure * config.export_window_competition_factor)
    return max(multiplier, 0.0)


def _resolve_regimes(
    rows: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]],
) -> List[str]:
    if regime_intervals is not None:
        regimes = []
        for item in regime_intervals:
            if isinstance(item, str):
                regimes.append(item)
            elif isinstance(item, dict):
                regimes.append(str(item["regime"]))
            elif hasattr(item, "regime"):
                regimes.append(str(getattr(item, "regime")))
            else:
                raise ValueError("could not extract regime")
        return regimes

    regimes = []
    for row in rows:
        if isinstance(row, dict) and "regime" in row:
            regimes.append(str(row["regime"]))
        elif hasattr(row, "regime"):
            regimes.append(str(getattr(row, "regime")))
        else:
            raise ValueError("regime_intervals must be supplied when rows do not contain regime")
    return regimes


def _extract_exported_energy(row: Dict[str, Any]) -> float:
    explicit = _extract_float(
        row,
        ["exported_energy", "energy_exported", "exported_kwh", "exported_mwh"],
        None,
    )
    if explicit is not None:
        return max(explicit, 0.0)
    signed_energy = _extract_float(row, ["energy_kwh", "energy_mwh"], None)
    if signed_energy is not None and signed_energy < 0:
        return abs(signed_energy)
    return 0.0


def _extract_charged_energy(row: Dict[str, Any]) -> float:
    explicit = _extract_float(
        row,
        ["charged_energy", "energy_charged", "charged_kwh", "charged_mwh"],
        None,
    )
    if explicit is not None:
        return max(explicit, 0.0)
    signed_energy = _extract_float(row, ["energy_kwh", "energy_mwh"], None)
    if signed_energy is not None and signed_energy > 0:
        return signed_energy
    return 0.0


def _extract_float(row: Dict[str, Any], fields: Sequence[str], default: Optional[float]) -> Optional[float]:
    for field in fields:
        if field in row and row[field] is not None:
            try:
                return float(row[field])
            except (TypeError, ValueError):
                continue
    return default


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
