"""Analyse realised battery profitability by classified market regime.

This module is analytical only. It joins existing dispatch/backtest rows with
market regime classifications and aggregates realised profitability metrics.
It does not create dispatch decisions or optimise strategy.
"""

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

from src.regime_analysis import REGIMES, RegimeAnalysisConfig, RegimeInterval, summarise_regimes


@dataclass(frozen=True)
class RegimeProfitabilityConfig:
    """Assumptions used only when fields are absent from dispatch rows."""

    battery_capacity_energy: Optional[float] = None
    degradation_cost_per_energy: Optional[float] = None
    price_field: Optional[str] = None
    profit_field: Optional[str] = None
    degradation_field: Optional[str] = None
    export_energy_field: Optional[str] = None
    charge_energy_field: Optional[str] = None
    spread_field: Optional[str] = None


def profitability_by_regime(
    dispatch_results: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]] = None,
    regime_config: Optional[RegimeAnalysisConfig] = None,
    profitability_config: Optional[RegimeProfitabilityConfig] = None,
) -> Dict[str, Any]:
    """Aggregate realised profitability metrics by market regime."""
    cfg = profitability_config or RegimeProfitabilityConfig()
    rows = list(dispatch_results)
    if not rows:
        raise ValueError("dispatch_results must contain at least one row")

    regimes = _resolve_regimes(rows, regime_intervals, regime_config, cfg.price_field)
    if len(regimes) != len(rows):
        raise ValueError("dispatch_results and regime_intervals must have the same length")

    aggregates = _initial_aggregates()
    total_profit = 0.0

    for row, regime in zip(rows, regimes):
        price = _extract_number(row, _price_fields(cfg), default=0.0)
        profit = _extract_number(row, _profit_fields(cfg), default=0.0)
        charged_energy = _extract_charged_energy(row, cfg)
        exported_energy = _extract_exported_energy(row, cfg)
        degradation = _extract_degradation(row, cfg, charged_energy + exported_energy)
        cycle_contribution = _extract_cycle_contribution(row, cfg, charged_energy + exported_energy)
        spread = _extract_spread(row, cfg)

        stats = aggregates[regime]
        stats["interval_count"] += 1
        stats["total_profit"] += profit
        stats["energy_exported"] += exported_energy
        stats["cycle_contribution"] += cycle_contribution
        stats["degradation_contribution"] += degradation
        stats["prices"].append(price)
        if spread is not None:
            stats["spreads"].append(spread)
        if charged_energy > 0:
            stats["charge_prices"].append(price)
        if exported_energy > 0:
            stats["export_prices"].append(price)

        total_profit += profit

    by_regime = {
        regime: _finalise_regime_stats(regime, stats, total_profit)
        for regime, stats in aggregates.items()
    }

    return {
        "total_profit": total_profit,
        "by_regime": by_regime,
        "profitable_regimes": [
            regime for regime, stats in by_regime.items()
            if stats["total_profit"] > 0
        ],
        "degradation_dominated_regimes": [
            regime for regime, stats in by_regime.items()
            if stats["degradation_dominates"]
        ],
        "top_pnl_regimes": sorted(
            by_regime,
            key=lambda regime: abs(by_regime[regime]["total_profit"]),
            reverse=True,
        ),
    }


def cycles_by_regime(
    dispatch_results: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]] = None,
    regime_config: Optional[RegimeAnalysisConfig] = None,
    profitability_config: Optional[RegimeProfitabilityConfig] = None,
) -> Dict[str, float]:
    """Return cycle contribution by regime."""
    summary = profitability_by_regime(
        dispatch_results,
        regime_intervals,
        regime_config,
        profitability_config,
    )
    return {
        regime: stats["cycle_contribution"]
        for regime, stats in summary["by_regime"].items()
    }


def export_activity_by_regime(
    dispatch_results: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]] = None,
    regime_config: Optional[RegimeAnalysisConfig] = None,
    profitability_config: Optional[RegimeProfitabilityConfig] = None,
) -> Dict[str, Dict[str, float]]:
    """Return exported energy and export interval counts by regime."""
    summary = profitability_by_regime(
        dispatch_results,
        regime_intervals,
        regime_config,
        profitability_config,
    )
    return {
        regime: {
            "energy_exported": stats["energy_exported"],
            "export_interval_count": stats["export_interval_count"],
        }
        for regime, stats in summary["by_regime"].items()
    }


def degradation_by_regime(
    dispatch_results: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]] = None,
    regime_config: Optional[RegimeAnalysisConfig] = None,
    profitability_config: Optional[RegimeProfitabilityConfig] = None,
) -> Dict[str, Dict[str, float]]:
    """Return degradation contribution and dominance flag by regime."""
    summary = profitability_by_regime(
        dispatch_results,
        regime_intervals,
        regime_config,
        profitability_config,
    )
    return {
        regime: {
            "degradation_contribution": stats["degradation_contribution"],
            "degradation_dominates": stats["degradation_dominates"],
        }
        for regime, stats in summary["by_regime"].items()
    }


def _resolve_regimes(
    rows: Sequence[Any],
    regime_intervals: Optional[Sequence[Any]],
    regime_config: Optional[RegimeAnalysisConfig],
    price_field: Optional[str],
) -> List[str]:
    if regime_intervals is None:
        classified = summarise_regimes(
            rows,
            regime_config,
            price_field=price_field,
        )["classified_intervals"]
        return [interval.regime for interval in classified]

    regimes = []
    for item in regime_intervals:
        if isinstance(item, str):
            regimes.append(item)
        elif isinstance(item, RegimeInterval):
            regimes.append(item.regime)
        elif isinstance(item, dict) and "regime" in item:
            regimes.append(str(item["regime"]))
        elif hasattr(item, "regime"):
            regimes.append(str(getattr(item, "regime")))
        else:
            raise ValueError("could not extract regime from regime_intervals item")
    return regimes


def _initial_aggregates() -> Dict[str, Dict[str, Any]]:
    return {
        regime: {
            "interval_count": 0,
            "total_profit": 0.0,
            "energy_exported": 0.0,
            "cycle_contribution": 0.0,
            "degradation_contribution": 0.0,
            "prices": [],
            "spreads": [],
            "charge_prices": [],
            "export_prices": [],
        }
        for regime in REGIMES
    }


def _finalise_regime_stats(
    regime: str,
    stats: Dict[str, Any],
    total_profit: float,
) -> Dict[str, Any]:
    export_interval_count = len(stats["export_prices"])
    average_profit = (
        stats["total_profit"] / stats["interval_count"]
        if stats["interval_count"]
        else 0.0
    )
    average_spread = _average_spread(stats)
    profitability_share = (
        stats["total_profit"] / total_profit
        if total_profit
        else 0.0
    )

    return {
        "regime": regime,
        "interval_count": stats["interval_count"],
        "average_profit": average_profit,
        "total_profit": stats["total_profit"],
        "average_spread_captured": average_spread,
        "energy_exported": stats["energy_exported"],
        "export_interval_count": export_interval_count,
        "cycle_contribution": stats["cycle_contribution"],
        "degradation_contribution": stats["degradation_contribution"],
        "profitability_share": profitability_share,
        "profitable": stats["total_profit"] > 0,
        "degradation_dominates": stats["degradation_contribution"] > max(stats["total_profit"], 0.0),
        "average_price": mean(stats["prices"]) if stats["prices"] else None,
    }


def _average_spread(stats: Dict[str, Any]) -> Optional[float]:
    if stats["spreads"]:
        return mean(stats["spreads"])
    if stats["charge_prices"] and stats["export_prices"]:
        return mean(stats["export_prices"]) - mean(stats["charge_prices"])
    return None


def _extract_exported_energy(row: Any, config: RegimeProfitabilityConfig) -> float:
    explicit = _extract_number(row, _export_energy_fields(config), default=None)
    if explicit is not None:
        return max(explicit, 0.0)

    signed_energy = _extract_number(row, ["energy_kwh", "energy_mwh"], default=None)
    if signed_energy is not None and signed_energy < 0:
        return abs(signed_energy)
    return 0.0


def _extract_charged_energy(row: Any, config: RegimeProfitabilityConfig) -> float:
    explicit = _extract_number(row, _charge_energy_fields(config), default=None)
    if explicit is not None:
        return max(explicit, 0.0)

    signed_energy = _extract_number(row, ["energy_kwh", "energy_mwh"], default=None)
    if signed_energy is not None and signed_energy > 0:
        return signed_energy
    return 0.0


def _extract_degradation(
    row: Any,
    config: RegimeProfitabilityConfig,
    throughput_energy: float,
) -> float:
    explicit = _extract_number(row, _degradation_fields(config), default=None)
    if explicit is not None:
        return max(explicit, 0.0)
    if config.degradation_cost_per_energy is not None:
        return throughput_energy * config.degradation_cost_per_energy
    return 0.0


def _extract_cycle_contribution(
    row: Any,
    config: RegimeProfitabilityConfig,
    throughput_energy: float,
) -> float:
    explicit = _extract_number(
        row,
        ["cycle_contribution", "cycles", "equivalent_cycles"],
        default=None,
    )
    if explicit is not None:
        return max(explicit, 0.0)
    if config.battery_capacity_energy:
        return throughput_energy / config.battery_capacity_energy
    return 0.0


def _extract_spread(row: Any, config: RegimeProfitabilityConfig) -> Optional[float]:
    return _extract_number(row, _spread_fields(config), default=None)


def _extract_number(row: Any, fields: Sequence[Optional[str]], default: Optional[float]) -> Optional[float]:
    for field in fields:
        if field is None:
            continue
        value = None
        if isinstance(row, dict) and field in row:
            value = row[field]
        elif hasattr(row, field):
            value = getattr(row, field)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _price_fields(config: RegimeProfitabilityConfig) -> List[Optional[str]]:
    return [
        config.price_field,
        "price",
        "price_per_kwh",
        "price_per_mwh",
        "RRP",
        "rrp",
    ]


def _profit_fields(config: RegimeProfitabilityConfig) -> List[Optional[str]]:
    return [
        config.profit_field,
        "profit",
        "cashflow",
        "net_cashflow",
        "arbitrage_profit",
        "net_profit",
        "net_revenue",
    ]


def _degradation_fields(config: RegimeProfitabilityConfig) -> List[Optional[str]]:
    return [
        config.degradation_field,
        "degradation_cost",
        "degradation",
        "degradation_contribution",
    ]


def _export_energy_fields(config: RegimeProfitabilityConfig) -> List[Optional[str]]:
    return [
        config.export_energy_field,
        "energy_exported",
        "exported_energy",
        "export_kwh",
        "export_mwh",
        "exported_kwh",
        "exported_mwh",
        "battery_discharged_kwh",
        "battery_discharged_mwh",
        "battery_discharged_arbitrage",
        "discharged_mwh",
    ]


def _charge_energy_fields(config: RegimeProfitabilityConfig) -> List[Optional[str]]:
    return [
        config.charge_energy_field,
        "energy_charged",
        "charged_energy",
        "charge_kwh",
        "charge_mwh",
        "charged_kwh",
        "charged_mwh",
        "battery_charged_kwh",
        "battery_charged_mwh",
        "battery_charged_arbitrage",
    ]


def _spread_fields(config: RegimeProfitabilityConfig) -> List[Optional[str]]:
    return [
        config.spread_field,
        "spread_captured",
        "captured_spread",
        "arbitrage_spread",
    ]
