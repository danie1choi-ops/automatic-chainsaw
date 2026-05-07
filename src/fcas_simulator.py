"""Simplified FCAS and energy arbitrage simulator for grid-scale batteries.

This module intentionally uses transparent assumptions instead of attempting to
replicate NEM dispatch, bidding, constraints, or FCAS causer-pays mechanics.
Prices are interpreted as $/MWh and FCAS availability as $/MW-hour.
"""

from dataclasses import dataclass, field
from math import sqrt
from statistics import mean
from typing import Dict, List, Optional, Sequence


HOURS_PER_YEAR = 8760.0


@dataclass(frozen=True)
class FCASActivationEvent:
    """Optional simplified FCAS activation event.

    direction:
        "raise" discharges the battery into the grid.
        "lower" charges the battery from the grid.
    interval_index:
        Zero-based index into the simulated price series.
    mw:
        Requested activation power.
    duration_hours:
        Duration of the activation inside the interval.
    price_per_mwh:
        Optional energy settlement price. If omitted, the interval energy price
        is used. This is not a separate FCAS enablement price.
    """

    interval_index: int
    direction: str
    mw: float
    duration_hours: float
    price_per_mwh: Optional[float] = None


@dataclass(frozen=True)
class FCASSimulatorConfig:
    """Configurable assumptions for the simplified simulator."""

    battery_capacity_mwh: float
    max_power_mw: float
    fcas_reservation_percent: float = 20.0
    degradation_cost_per_mwh: float = 0.0
    round_trip_efficiency: float = 0.88
    interval_hours: float = 5.0 / 60.0
    initial_soc_percent: float = 50.0
    min_soc_percent: float = 10.0
    max_soc_percent: float = 90.0
    charge_price_threshold_per_mwh: float = 60.0
    discharge_price_threshold_per_mwh: float = 160.0
    fcas_availability_price_per_mw_hour: float = 8.0
    annualise_results: bool = True

    def validate(self) -> None:
        """Validate core physical and modelling inputs."""
        if self.battery_capacity_mwh <= 0:
            raise ValueError("battery_capacity_mwh must be greater than zero")
        if self.max_power_mw <= 0:
            raise ValueError("max_power_mw must be greater than zero")
        if not 0 <= self.fcas_reservation_percent <= 100:
            raise ValueError("fcas_reservation_percent must be between 0 and 100")
        if self.degradation_cost_per_mwh < 0:
            raise ValueError("degradation_cost_per_mwh cannot be negative")
        if not 0 < self.round_trip_efficiency <= 1:
            raise ValueError("round_trip_efficiency must be in the range (0, 1]")
        if self.interval_hours <= 0:
            raise ValueError("interval_hours must be greater than zero")
        if not 0 <= self.min_soc_percent <= self.initial_soc_percent <= self.max_soc_percent <= 100:
            raise ValueError("SoC percentages must satisfy min <= initial <= max within 0..100")
        if self.charge_price_threshold_per_mwh > self.discharge_price_threshold_per_mwh:
            raise ValueError("charge threshold should not exceed discharge threshold")
        if self.fcas_availability_price_per_mw_hour < 0:
            raise ValueError("fcas_availability_price_per_mw_hour cannot be negative")


@dataclass
class RevenueBreakdown:
    """Revenue and cost components in dollars."""

    arbitrage_revenue: float = 0.0
    arbitrage_charge_cost: float = 0.0
    fcas_enablement_revenue: float = 0.0
    fcas_activation_revenue: float = 0.0
    degradation_cost: float = 0.0

    @property
    def gross_revenue(self) -> float:
        """Revenue before charge and degradation costs."""
        return (
            self.arbitrage_revenue
            + self.fcas_enablement_revenue
            + self.fcas_activation_revenue
        )

    @property
    def net_revenue(self) -> float:
        """Net revenue after charge and degradation costs."""
        return self.gross_revenue - self.arbitrage_charge_cost - self.degradation_cost

    def annualised(self, factor: float) -> "RevenueBreakdown":
        """Return a copy scaled by an annualisation factor."""
        return RevenueBreakdown(
            arbitrage_revenue=self.arbitrage_revenue * factor,
            arbitrage_charge_cost=self.arbitrage_charge_cost * factor,
            fcas_enablement_revenue=self.fcas_enablement_revenue * factor,
            fcas_activation_revenue=self.fcas_activation_revenue * factor,
            degradation_cost=self.degradation_cost * factor,
        )


@dataclass
class SimulationResult:
    """Summary output for one scenario."""

    scenario: str
    annual_revenue: float
    simulated_net_revenue: float
    cycles: float
    degradation_cost: float
    utilisation: float
    revenue_breakdown: RevenueBreakdown
    assumptions: Dict[str, float]
    interval_count: int
    ending_soc_mwh: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class DispatchState:
    """Internal mutable dispatch state."""

    soc_mwh: float
    charged_mwh: float = 0.0
    discharged_mwh: float = 0.0
    utilised_mw_hours: float = 0.0


def simulate_arbitrage_only(
    energy_prices_per_mwh: Sequence[float],
    config: FCASSimulatorConfig,
) -> SimulationResult:
    """Simulate energy arbitrage without FCAS reservation or enablement."""
    return _simulate(
        scenario="arbitrage_only",
        energy_prices_per_mwh=energy_prices_per_mwh,
        config=config,
        include_arbitrage=True,
        include_fcas=False,
        activation_events=None,
    )


def simulate_fcas_only(
    energy_prices_per_mwh: Sequence[float],
    config: FCASSimulatorConfig,
    activation_events: Optional[Sequence[FCASActivationEvent]] = None,
) -> SimulationResult:
    """Simulate FCAS enablement and optional activation without arbitrage."""
    return _simulate(
        scenario="fcas_only",
        energy_prices_per_mwh=energy_prices_per_mwh,
        config=config,
        include_arbitrage=False,
        include_fcas=True,
        activation_events=activation_events,
    )


def simulate_stacked_revenue(
    energy_prices_per_mwh: Sequence[float],
    config: FCASSimulatorConfig,
    activation_events: Optional[Sequence[FCASActivationEvent]] = None,
) -> SimulationResult:
    """Simulate arbitrage with FCAS power and energy reserved."""
    return _simulate(
        scenario="stacked_revenue",
        energy_prices_per_mwh=energy_prices_per_mwh,
        config=config,
        include_arbitrage=True,
        include_fcas=True,
        activation_events=activation_events,
    )


def compare_revenue_cases(
    energy_prices_per_mwh: Sequence[float],
    config: FCASSimulatorConfig,
    activation_events: Optional[Sequence[FCASActivationEvent]] = None,
) -> Dict[str, SimulationResult]:
    """Compare arbitrage-only, FCAS-only, and stacked revenue cases."""
    return {
        "arbitrage_only": simulate_arbitrage_only(energy_prices_per_mwh, config),
        "fcas_only": simulate_fcas_only(energy_prices_per_mwh, config, activation_events),
        "stacked_revenue": simulate_stacked_revenue(
            energy_prices_per_mwh,
            config,
            activation_events,
        ),
    }


def _simulate(
    scenario: str,
    energy_prices_per_mwh: Sequence[float],
    config: FCASSimulatorConfig,
    include_arbitrage: bool,
    include_fcas: bool,
    activation_events: Optional[Sequence[FCASActivationEvent]],
) -> SimulationResult:
    config.validate()
    prices = [float(price) for price in energy_prices_per_mwh]
    if not prices:
        raise ValueError("energy_prices_per_mwh must contain at least one price")

    events_by_interval = _group_activation_events(activation_events or [], len(prices))
    state = DispatchState(soc_mwh=config.battery_capacity_mwh * config.initial_soc_percent / 100.0)
    breakdown = RevenueBreakdown()
    warnings: List[str] = []

    reserved_power_mw = _reserved_power_mw(config) if include_fcas else 0.0
    arbitrage_power_mw = max(config.max_power_mw - reserved_power_mw, 0.0)
    reserve_energy_mwh = _reserved_energy_mwh(config) if include_fcas else 0.0
    min_soc_mwh = config.battery_capacity_mwh * config.min_soc_percent / 100.0
    max_soc_mwh = config.battery_capacity_mwh * config.max_soc_percent / 100.0

    for interval_index, price in enumerate(prices):
        if include_fcas:
            breakdown.fcas_enablement_revenue += (
                reserved_power_mw
                * config.fcas_availability_price_per_mw_hour
                * config.interval_hours
            )
            state.utilised_mw_hours += reserved_power_mw * config.interval_hours

        for event in events_by_interval.get(interval_index, []):
            _apply_activation_event(
                event=event,
                interval_price_per_mwh=price,
                config=config,
                state=state,
                breakdown=breakdown,
                min_soc_mwh=min_soc_mwh,
                max_soc_mwh=max_soc_mwh,
                reserved_power_mw=reserved_power_mw,
                warnings=warnings,
            )

        if include_arbitrage and arbitrage_power_mw > 0:
            _apply_arbitrage_dispatch(
                price_per_mwh=price,
                config=config,
                state=state,
                breakdown=breakdown,
                min_dispatch_soc_mwh=min_soc_mwh + reserve_energy_mwh,
                max_dispatch_soc_mwh=max_soc_mwh - reserve_energy_mwh,
                arbitrage_power_mw=arbitrage_power_mw,
            )

    throughput_mwh = state.charged_mwh + state.discharged_mwh
    breakdown.degradation_cost = throughput_mwh * config.degradation_cost_per_mwh
    simulated_hours = len(prices) * config.interval_hours
    annualisation_factor = HOURS_PER_YEAR / simulated_hours if config.annualise_results else 1.0
    annual_breakdown = breakdown.annualised(annualisation_factor)
    cycles = throughput_mwh / (2.0 * config.battery_capacity_mwh)
    utilisation = state.utilised_mw_hours / (config.max_power_mw * simulated_hours)

    return SimulationResult(
        scenario=scenario,
        annual_revenue=annual_breakdown.net_revenue,
        simulated_net_revenue=breakdown.net_revenue,
        cycles=cycles * annualisation_factor,
        degradation_cost=annual_breakdown.degradation_cost,
        utilisation=utilisation,
        revenue_breakdown=annual_breakdown,
        assumptions=_assumptions(config, annualisation_factor),
        interval_count=len(prices),
        ending_soc_mwh=state.soc_mwh,
        warnings=warnings,
    )


def _apply_arbitrage_dispatch(
    price_per_mwh: float,
    config: FCASSimulatorConfig,
    state: DispatchState,
    breakdown: RevenueBreakdown,
    min_dispatch_soc_mwh: float,
    max_dispatch_soc_mwh: float,
    arbitrage_power_mw: float,
) -> None:
    charge_efficiency = sqrt(config.round_trip_efficiency)
    discharge_efficiency = sqrt(config.round_trip_efficiency)
    interval_power_mwh = arbitrage_power_mw * config.interval_hours

    if price_per_mwh <= config.charge_price_threshold_per_mwh:
        room_mwh = max(max_dispatch_soc_mwh - state.soc_mwh, 0.0)
        battery_charge_mwh = min(interval_power_mwh * charge_efficiency, room_mwh)
        grid_import_mwh = battery_charge_mwh / charge_efficiency if charge_efficiency else 0.0
        state.soc_mwh += battery_charge_mwh
        state.charged_mwh += battery_charge_mwh
        state.utilised_mw_hours += grid_import_mwh
        breakdown.arbitrage_charge_cost += grid_import_mwh * price_per_mwh

    elif price_per_mwh >= config.discharge_price_threshold_per_mwh:
        available_mwh = max(state.soc_mwh - min_dispatch_soc_mwh, 0.0)
        battery_discharge_mwh = min(interval_power_mwh, available_mwh)
        grid_export_mwh = battery_discharge_mwh * discharge_efficiency
        state.soc_mwh -= battery_discharge_mwh
        state.discharged_mwh += battery_discharge_mwh
        state.utilised_mw_hours += battery_discharge_mwh
        breakdown.arbitrage_revenue += grid_export_mwh * price_per_mwh


def _apply_activation_event(
    event: FCASActivationEvent,
    interval_price_per_mwh: float,
    config: FCASSimulatorConfig,
    state: DispatchState,
    breakdown: RevenueBreakdown,
    min_soc_mwh: float,
    max_soc_mwh: float,
    reserved_power_mw: float,
    warnings: List[str],
) -> None:
    if event.direction not in {"raise", "lower"}:
        raise ValueError("activation event direction must be 'raise' or 'lower'")
    if event.mw < 0:
        raise ValueError("activation event mw cannot be negative")
    if event.duration_hours < 0:
        raise ValueError("activation event duration_hours cannot be negative")

    activation_mw = min(event.mw, reserved_power_mw)
    if event.mw > reserved_power_mw:
        warnings.append(
            f"Activation at interval {event.interval_index} capped to reserved FCAS MW."
        )

    requested_mwh = activation_mw * min(event.duration_hours, config.interval_hours)
    settlement_price = event.price_per_mwh
    if settlement_price is None:
        settlement_price = interval_price_per_mwh

    charge_efficiency = sqrt(config.round_trip_efficiency)
    discharge_efficiency = sqrt(config.round_trip_efficiency)

    if event.direction == "raise":
        battery_discharge_mwh = min(requested_mwh, max(state.soc_mwh - min_soc_mwh, 0.0))
        grid_export_mwh = battery_discharge_mwh * discharge_efficiency
        state.soc_mwh -= battery_discharge_mwh
        state.discharged_mwh += battery_discharge_mwh
        state.utilised_mw_hours += battery_discharge_mwh
        breakdown.fcas_activation_revenue += grid_export_mwh * settlement_price
    else:
        room_mwh = max(max_soc_mwh - state.soc_mwh, 0.0)
        battery_charge_mwh = min(requested_mwh * charge_efficiency, room_mwh)
        grid_import_mwh = battery_charge_mwh / charge_efficiency if charge_efficiency else 0.0
        state.soc_mwh += battery_charge_mwh
        state.charged_mwh += battery_charge_mwh
        state.utilised_mw_hours += grid_import_mwh
        breakdown.fcas_activation_revenue -= grid_import_mwh * settlement_price


def _group_activation_events(
    activation_events: Sequence[FCASActivationEvent],
    interval_count: int,
) -> Dict[int, List[FCASActivationEvent]]:
    events_by_interval: Dict[int, List[FCASActivationEvent]] = {}
    for event in activation_events:
        if not 0 <= event.interval_index < interval_count:
            raise ValueError("activation event interval_index is outside the price series")
        events_by_interval.setdefault(event.interval_index, []).append(event)
    return events_by_interval


def _reserved_power_mw(config: FCASSimulatorConfig) -> float:
    return config.max_power_mw * config.fcas_reservation_percent / 100.0


def _reserved_energy_mwh(config: FCASSimulatorConfig) -> float:
    return config.battery_capacity_mwh * config.fcas_reservation_percent / 100.0


def _assumptions(config: FCASSimulatorConfig, annualisation_factor: float) -> Dict[str, float]:
    return {
        "battery_capacity_mwh": config.battery_capacity_mwh,
        "max_power_mw": config.max_power_mw,
        "fcas_reservation_percent": config.fcas_reservation_percent,
        "degradation_cost_per_mwh": config.degradation_cost_per_mwh,
        "round_trip_efficiency": config.round_trip_efficiency,
        "interval_hours": config.interval_hours,
        "charge_price_threshold_per_mwh": config.charge_price_threshold_per_mwh,
        "discharge_price_threshold_per_mwh": config.discharge_price_threshold_per_mwh,
        "fcas_availability_price_per_mw_hour": config.fcas_availability_price_per_mw_hour,
        "annualisation_factor": annualisation_factor,
    }


def format_comparison_summary(results: Dict[str, SimulationResult]) -> str:
    """Format comparison results as a small text table."""
    lines = [
        "scenario,annual_revenue,cycles,degradation_cost,utilisation",
    ]
    for scenario, result in results.items():
        lines.append(
            ",".join(
                [
                    scenario,
                    f"{result.annual_revenue:.2f}",
                    f"{result.cycles:.3f}",
                    f"{result.degradation_cost:.2f}",
                    f"{result.utilisation:.3f}",
                ]
            )
        )
    return "\n".join(lines)


def average_price(energy_prices_per_mwh: Sequence[float]) -> float:
    """Small helper for future extensions and documentation examples."""
    if not energy_prices_per_mwh:
        raise ValueError("energy_prices_per_mwh must contain at least one price")
    return mean(float(price) for price in energy_prices_per_mwh)
