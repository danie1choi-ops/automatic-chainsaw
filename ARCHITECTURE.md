# Architecture

This project currently contains two separate modelling systems:

- residential solar and tariff optimisation
- grid-scale battery arbitrage and FCAS revenue modelling

They share battery concepts, but they are not the same market model and should stay separated unless a future abstraction is clearly useful.

## 1. Residential System

The residential system models behind-the-meter behaviour for a household battery and solar setup.

Core modules:

- `src/solar_load_model.py`
- `src/solar_backtest.py`
- `src/tariff_scenarios.py`
- `src/battery_model.py`
- `src/strategy.py`
- `src/backtest.py`

Main concepts:

- solar generation: estimated or simulated household PV output
- household load: demand profile consumed behind the meter
- home battery: kWh-scale storage with SoC limits, charge/discharge power limits, and round-trip efficiency
- tariff optimisation: comparison of retail tariff structures, import costs, export credits, and scenario outcomes
- optional arbitrage: price-responsive charging/exporting where the residential model has price signals available

The residential model is primarily concerned with customer bill impact and behind-the-meter dispatch. It should not assume direct FCAS access or wholesale market participation unless explicitly modelled through a separate VPP or aggregation layer.

## 2. Grid-Scale System

The grid-scale system models a utility-scale battery participating in wholesale energy arbitrage and simplified FCAS enablement.

Core module:

- `src/fcas_simulator.py`

Main concepts:

- wholesale arbitrage: charge at low `$ / MWh` prices and discharge at high `$ / MWh` prices
- FCAS participation: reserve battery capability and earn fixed `$ / MW-hour` availability revenue
- stacked revenues: combine arbitrage with FCAS enablement, while reducing arbitrage headroom for reserved FCAS capacity
- battery reservation: reserve a configurable percentage of power and energy capacity for FCAS
- activation events: optional simplified raise/lower events that move energy and settle at a configured or interval energy price

The grid-scale model is intentionally simplified. It is a transparent planning simulator, not a NEM dispatch engine.

## 3. Shared Components

The two systems share modelling concepts rather than a single unified architecture.

Shared concepts:

- battery degradation: cost applied to energy throughput
- efficiency: round-trip efficiency affects usable energy and revenue
- cycle accounting: equivalent full cycles are derived from charge/discharge throughput
- dispatch logic: actions are constrained by SoC, power limits, interval duration, and available capacity

Current implementation split:

- residential battery behaviour is represented by `BatteryModel` in `src/battery_model.py`
- grid-scale dispatch state and FCAS accounting are local to `src/fcas_simulator.py`

This split keeps residential tariff modelling independent from grid-scale market assumptions.

## 4. Current Limitations

- Residential and grid-scale systems do not share a formal battery interface.
- Residential arbitrage uses simplified threshold logic.
- Grid-scale arbitrage uses fixed charge/discharge thresholds, not optimisation.
- FCAS is represented as a single generic availability product.
- FCAS enablement uses a fixed price, not historical FCAS market prices.
- FCAS activation events are manually supplied and simplified.
- Network constraints, loss factors, bidding, rebidding, dispatch targets, and settlement rules are not modelled.
- Degradation is throughput-based only; calendar ageing and capacity fade are not modelled.
- Forecast uncertainty, outages, and operational constraints are not included.
- Outputs are summary-oriented rather than full audit-grade interval ledgers for every model.

## 5. Future Research Ideas

- Define a shared battery protocol for capacity, power, efficiency, SoC, throughput, and cycle accounting.
- Add optimisation-based dispatch for residential tariffs and wholesale arbitrage.
- Add separate FCAS products for raise/lower, regulation, and contingency services.
- Load historical FCAS prices and compare energy-only versus FCAS-heavy operating strategies.
- Model FCAS reservation by direction, with separate raise and lower SoC requirements.
- Add VPP aggregation to connect residential batteries to grid-scale services.
- Track interval-level ledgers for all simulations.
- Add degradation models based on depth of discharge, C-rate, temperature, and capacity fade.
- Add sensitivity analysis for battery duration, reservation percentage, degradation cost, and efficiency.
- Compare simple threshold dispatch against co-optimised arbitrage and FCAS strategies.
