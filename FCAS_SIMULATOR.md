# Simplified FCAS Simulator

`src/fcas_simulator.py` models a grid-scale battery with three revenue cases:

- `arbitrage_only`: charge below a configured energy price threshold and discharge above another threshold.
- `fcas_only`: reserve a share of battery power/capacity and earn a fixed availability payment.
- `stacked_revenue`: combine arbitrage with reserved FCAS headroom.

This is a transparent planning model, not a NEM dispatch replica.

## Main Assumptions

- Energy prices are supplied as `$ / MWh`.
- FCAS availability revenue is supplied as `$ / MW-hour`.
- Dispatch uses a fixed interval length, defaulting to 5 minutes.
- FCAS reservation is a simple percentage of both battery power and battery energy capacity.
- Reserved FCAS power is unavailable for arbitrage in the stacked case.
- Reserved FCAS energy narrows the arbitrage state-of-charge band in the stacked case.
- Round-trip efficiency is split evenly across charging and discharging using `sqrt(round_trip_efficiency)`.
- Degradation cost is charged per MWh of battery-side throughput.
- Equivalent cycles are calculated as `throughput_mwh / (2 * battery_capacity_mwh)`.
- Results are annualised by default using `8760 / simulated_hours`.

## What It Does Not Model

- FCAS bid stacks, AEMO dispatch targets, enablement limits, trapeziums, or causer-pays factors.
- Separate raise/lower/regulation/contingency FCAS products.
- Network constraints, marginal loss factors, bidding strategy, rebidding, or settlement details.
- Forecasting, price optimisation, state-of-charge co-optimisation, or risk management.
- Calendar degradation, capacity fade, outages, auxiliary load, taxes, fees, or capex.

## Configurable Inputs

Use `FCASSimulatorConfig`:

- `battery_capacity_mwh`
- `max_power_mw`
- `fcas_reservation_percent`
- `degradation_cost_per_mwh`
- `round_trip_efficiency`
- `interval_hours`
- `initial_soc_percent`
- `min_soc_percent`
- `max_soc_percent`
- `charge_price_threshold_per_mwh`
- `discharge_price_threshold_per_mwh`
- `fcas_availability_price_per_mw_hour`
- `annualise_results`

## Optional FCAS Activation Events

`FCASActivationEvent` can represent simplified raise or lower activation:

- `raise`: discharges the battery and receives energy settlement revenue.
- `lower`: charges the battery and pays for energy settlement.

Activation events are capped to the configured reserved FCAS MW. If an event does
not provide its own `price_per_mwh`, the interval energy price is used.

## Example

```python
from src.fcas_simulator import FCASSimulatorConfig, compare_revenue_cases

prices = [40.0, 45.0, 180.0, 220.0]  # $/MWh

config = FCASSimulatorConfig(
    battery_capacity_mwh=100.0,
    max_power_mw=50.0,
    fcas_reservation_percent=20.0,
    degradation_cost_per_mwh=5.0,
    round_trip_efficiency=0.88,
    fcas_availability_price_per_mw_hour=8.0,
    annualise_results=False,
)

results = compare_revenue_cases(prices, config)

for scenario, result in results.items():
    print(scenario, result.annual_revenue, result.cycles)
```

## Output Fields

Each simulation returns a `SimulationResult`:

- `annual_revenue`
- `simulated_net_revenue`
- `cycles`
- `degradation_cost`
- `utilisation`
- `revenue_breakdown`
- `assumptions`
- `interval_count`
- `ending_soc_mwh`
- `warnings`

`revenue_breakdown` separates:

- arbitrage discharge revenue
- arbitrage charge cost
- FCAS enablement revenue
- FCAS activation revenue
- degradation cost

## Extension Points

The module is intentionally small and modular. Likely next steps are:

- add separate FCAS products and prices
- replace threshold arbitrage with an optimiser
- add historical FCAS price inputs
- track activation energy separately from arbitrage throughput
- add state-of-charge constraints by FCAS direction
- introduce capacity fade and availability outages
