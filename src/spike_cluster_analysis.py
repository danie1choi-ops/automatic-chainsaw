"""Analyse battery behaviour during clustered price spikes.

This module is analytical only. It reads realised backtest/live-observation
rows, detects clusters of price-spike intervals, and estimates whether exports
were missed because the simulated battery had already reached MIN_SOC. It does
not change strategy decisions, dispatch rules, or any hardware-control path.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

from src import config as default_config
from src.regime_analysis import PRICE_SPIKE


@dataclass(frozen=True)
class SpikeClusterAnalysisConfig:
    """Configuration for analytical spike cluster detection."""

    max_gap_intervals: int = 1
    min_cluster_size: int = 2
    spike_price_threshold: float = default_config.EXPORT_PRICE_THRESHOLD
    min_soc_percent: float = default_config.MIN_SOC_PERCENT
    battery_capacity_kwh: float = default_config.BATTERY_CAPACITY_KWH
    max_discharge_kw: float = default_config.MAX_DISCHARGE_KW
    degradation_cost_per_kwh: float = default_config.DEGRADATION_COST_PER_KWH
    interval_hours: float = default_config.INTERVAL_MINUTES / 60.0
    timestamp_field: Optional[str] = None
    price_field: Optional[str] = None
    regime_field: Optional[str] = None
    action_field: Optional[str] = None
    soc_field: Optional[str] = None
    cashflow_field: Optional[str] = None
    energy_field: Optional[str] = None

    def validate(self) -> None:
        if self.max_gap_intervals < 0:
            raise ValueError("max_gap_intervals must be non-negative")
        if self.min_cluster_size <= 0:
            raise ValueError("min_cluster_size must be greater than zero")
        if self.interval_hours <= 0:
            raise ValueError("interval_hours must be greater than zero")
        if self.battery_capacity_kwh <= 0:
            raise ValueError("battery_capacity_kwh must be greater than zero")
        if self.max_discharge_kw <= 0:
            raise ValueError("max_discharge_kw must be greater than zero")


@dataclass(frozen=True)
class SpikeCluster:
    """Metrics for one cluster of price-spike intervals."""

    start_timestamp: Optional[datetime]
    end_timestamp: Optional[datetime]
    spike_interval_count: int
    max_price: float
    average_spike_price: float
    first_export_timestamp: Optional[datetime]
    last_export_timestamp: Optional[datetime]
    starting_soc: Optional[float]
    ending_soc: Optional[float]
    export_count: int
    missed_spike_exports_due_to_min_soc: int
    realised_cashflow: float
    theoretical_cashflow_if_reserved: float


def load_output_rows(path: Path | str) -> List[Dict[str, str]]:
    """Load an existing CSV output file as analysis input rows."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_default_output_rows(
    backtest_path: Path | str = Path("outputs/backtest_results.csv"),
    live_observation_path: Path | str = Path("outputs/live_observation.csv"),
) -> List[Dict[str, str]]:
    """Load backtest and live-observation outputs when present."""
    rows: List[Dict[str, str]] = []
    for path in (backtest_path, live_observation_path):
        output_path = Path(path)
        if output_path.exists():
            source_rows = load_output_rows(output_path)
            for row in source_rows:
                row.setdefault("source_file", str(output_path))
            rows.extend(source_rows)
    return rows


def analyse_spike_clusters(
    rows: Sequence[Any],
    analysis_config: Optional[SpikeClusterAnalysisConfig] = None,
) -> List[SpikeCluster]:
    """Detect spike clusters and calculate realised/reserved-energy metrics."""
    cfg = analysis_config or SpikeClusterAnalysisConfig()
    cfg.validate()

    parsed_rows = [_parse_row(index, row, cfg) for index, row in enumerate(rows)]
    spike_rows = [row for row in parsed_rows if row["is_spike"]]
    clusters = _cluster_spike_rows(spike_rows, cfg)

    return [
        _analyse_cluster(cluster_rows, cfg)
        for cluster_rows in clusters
        if len(cluster_rows) >= cfg.min_cluster_size
    ]


def summarise_spike_clusters(
    clusters_or_rows: Sequence[Any],
    analysis_config: Optional[SpikeClusterAnalysisConfig] = None,
) -> Dict[str, Any]:
    """Summarise cluster-level SoC exhaustion and missed-cashflow metrics."""
    clusters = _coerce_clusters(clusters_or_rows, analysis_config)
    if not clusters:
        return {
            "total_clusters": 0,
            "average_cluster_duration_hours": 0.0,
            "average_soc_drawdown": 0.0,
            "missed_spike_count": 0,
            "estimated_missed_cashflow": 0.0,
            "percentage_clusters_ending_at_min_soc": 0.0,
        }

    cfg = analysis_config or SpikeClusterAnalysisConfig()
    durations = [_duration_hours(cluster, cfg) for cluster in clusters]
    drawdowns = [
        cluster.starting_soc - cluster.ending_soc
        for cluster in clusters
        if cluster.starting_soc is not None and cluster.ending_soc is not None
    ]
    missed_cashflow = sum(
        max(0.0, cluster.theoretical_cashflow_if_reserved - cluster.realised_cashflow)
        for cluster in clusters
    )
    clusters_ending_at_min = sum(
        1
        for cluster in clusters
        if cluster.ending_soc is not None and cluster.ending_soc <= cfg.min_soc_percent
    )

    return {
        "total_clusters": len(clusters),
        "average_cluster_duration_hours": mean(durations) if durations else 0.0,
        "average_soc_drawdown": mean(drawdowns) if drawdowns else 0.0,
        "missed_spike_count": sum(
            cluster.missed_spike_exports_due_to_min_soc for cluster in clusters
        ),
        "estimated_missed_cashflow": missed_cashflow,
        "percentage_clusters_ending_at_min_soc": (
            clusters_ending_at_min / len(clusters) * 100.0
        ),
    }


def _cluster_spike_rows(
    spike_rows: Sequence[Dict[str, Any]],
    cfg: SpikeClusterAnalysisConfig,
) -> List[List[Dict[str, Any]]]:
    clusters: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    for row in spike_rows:
        if not current:
            current = [row]
            continue

        non_spike_gap = row["index"] - current[-1]["index"] - 1
        same_source = row["source"] == current[-1]["source"]
        if same_source and non_spike_gap <= cfg.max_gap_intervals:
            current.append(row)
        else:
            clusters.append(current)
            current = [row]

    if current:
        clusters.append(current)
    return clusters


def _analyse_cluster(
    cluster_rows: Sequence[Dict[str, Any]],
    cfg: SpikeClusterAnalysisConfig,
) -> SpikeCluster:
    exports = [row for row in cluster_rows if row["action"] == "EXPORT"]
    prices = [row["price"] for row in cluster_rows]
    soc_values = [row["soc"] for row in cluster_rows if row["soc"] is not None]
    realised_cashflow = sum(row["cashflow"] for row in cluster_rows)
    theoretical_cashflow = _theoretical_reserved_cashflow(cluster_rows, cfg)

    return SpikeCluster(
        start_timestamp=cluster_rows[0]["timestamp"],
        end_timestamp=cluster_rows[-1]["timestamp"],
        spike_interval_count=len(cluster_rows),
        max_price=max(prices),
        average_spike_price=mean(prices),
        first_export_timestamp=exports[0]["timestamp"] if exports else None,
        last_export_timestamp=exports[-1]["timestamp"] if exports else None,
        starting_soc=_estimate_starting_soc(cluster_rows[0], cfg),
        ending_soc=soc_values[-1] if soc_values else None,
        export_count=len(exports),
        missed_spike_exports_due_to_min_soc=sum(
            1 for row in cluster_rows if _missed_due_to_min_soc(row, cfg)
        ),
        realised_cashflow=realised_cashflow,
        theoretical_cashflow_if_reserved=theoretical_cashflow,
    )


def _theoretical_reserved_cashflow(
    cluster_rows: Sequence[Dict[str, Any]],
    cfg: SpikeClusterAnalysisConfig,
) -> float:
    starting_soc = _estimate_starting_soc(cluster_rows[0], cfg)
    if starting_soc is None:
        return 0.0

    reserve_kwh = max(0.0, starting_soc - cfg.min_soc_percent) / 100.0
    reserve_kwh *= cfg.battery_capacity_kwh
    interval_limit_kwh = cfg.max_discharge_kw * cfg.interval_hours
    theoretical_cashflow = 0.0

    for row in cluster_rows:
        export_kwh = min(interval_limit_kwh, reserve_kwh)
        if export_kwh <= 0:
            break
        theoretical_cashflow += export_kwh * row["price"]
        theoretical_cashflow -= export_kwh * cfg.degradation_cost_per_kwh
        reserve_kwh -= export_kwh

    return theoretical_cashflow


def _estimate_starting_soc(
    first_cluster_row: Dict[str, Any],
    cfg: SpikeClusterAnalysisConfig,
) -> Optional[float]:
    soc = first_cluster_row["soc"]
    if soc is None:
        return None

    if first_cluster_row["action"] != "EXPORT":
        return soc

    exported_kwh = max(0.0, -first_cluster_row["energy"])
    if exported_kwh == 0.0:
        return soc
    return soc + exported_kwh / cfg.battery_capacity_kwh * 100.0


def _missed_due_to_min_soc(
    row: Dict[str, Any],
    cfg: SpikeClusterAnalysisConfig,
) -> bool:
    if row["action"] == "EXPORT":
        return False
    if row["soc"] is not None and row["soc"] <= cfg.min_soc_percent:
        return True
    return "min soc" in row["reason"].lower()


def _parse_row(
    index: int,
    row: Any,
    cfg: SpikeClusterAnalysisConfig,
) -> Dict[str, Any]:
    price = _extract_number(row, _price_fields(cfg), default=None)
    if price is None:
        raise ValueError("could not extract price from row")

    regime = _extract_string(row, _regime_fields(cfg))
    is_spike = regime == PRICE_SPIKE if regime is not None else price >= cfg.spike_price_threshold

    return {
        "index": index,
        "timestamp": _extract_timestamp(row, cfg.timestamp_field),
        "source": _extract_string(row, ["source_file", "source"], default=None),
        "price": price,
        "is_spike": is_spike,
        "action": _extract_string(row, _action_fields(cfg), default="").upper(),
        "soc": _extract_number(row, _soc_fields(cfg), default=None),
        "cashflow": _extract_number(row, _cashflow_fields(cfg), default=0.0),
        "energy": _extract_number(row, _energy_fields(cfg), default=0.0),
        "reason": _extract_string(row, ["reason"], default=""),
    }


def _coerce_clusters(
    clusters_or_rows: Sequence[Any],
    analysis_config: Optional[SpikeClusterAnalysisConfig],
) -> List[SpikeCluster]:
    items = list(clusters_or_rows)
    if not items:
        return []
    if all(isinstance(item, SpikeCluster) for item in items):
        return items
    return analyse_spike_clusters(items, analysis_config)


def _duration_hours(cluster: SpikeCluster, cfg: SpikeClusterAnalysisConfig) -> float:
    if cluster.start_timestamp is not None and cluster.end_timestamp is not None:
        duration = cluster.end_timestamp - cluster.start_timestamp
        return duration.total_seconds() / 3600.0 + cfg.interval_hours
    return cluster.spike_interval_count * cfg.interval_hours


def _extract_timestamp(row: Any, explicit_field: Optional[str]) -> Optional[datetime]:
    value = _extract_value(row, [explicit_field, "timestamp", "datetime", "time"])
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _extract_number(
    row: Any,
    fields: Sequence[Optional[str]],
    default: Optional[float],
) -> Optional[float]:
    value = _extract_value(row, fields)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_string(
    row: Any,
    fields: Sequence[Optional[str]],
    default: Optional[str] = None,
) -> Optional[str]:
    value = _extract_value(row, fields)
    if value is None:
        return default
    return str(value)


def _extract_value(row: Any, fields: Sequence[Optional[str]]) -> Any:
    for field in fields:
        if field is None:
            continue
        if isinstance(row, dict) and field in row:
            return row[field]
        if hasattr(row, field):
            return getattr(row, field)
    return None


def _price_fields(cfg: SpikeClusterAnalysisConfig) -> List[Optional[str]]:
    return [cfg.price_field, "price", "price_per_kwh", "price_per_mwh", "RRP", "rrp"]


def _regime_fields(cfg: SpikeClusterAnalysisConfig) -> List[Optional[str]]:
    return [cfg.regime_field, "regime", "market_regime", "price_regime"]


def _action_fields(cfg: SpikeClusterAnalysisConfig) -> List[Optional[str]]:
    return [cfg.action_field, "action", "dispatch_action", "decision"]


def _soc_fields(cfg: SpikeClusterAnalysisConfig) -> List[Optional[str]]:
    return [cfg.soc_field, "soc_percent", "simulated_soc", "soc", "battery_soc_percent"]


def _cashflow_fields(cfg: SpikeClusterAnalysisConfig) -> List[Optional[str]]:
    return [
        cfg.cashflow_field,
        "cashflow",
        "simulated_cashflow",
        "net_cashflow",
        "profit",
        "net_profit",
    ]


def _energy_fields(cfg: SpikeClusterAnalysisConfig) -> List[Optional[str]]:
    return [
        cfg.energy_field,
        "energy_kwh",
        "exported_kwh",
        "export_kwh",
        "battery_discharged_kwh",
    ]
