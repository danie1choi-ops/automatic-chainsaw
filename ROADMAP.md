# Roadmap

This repository is organised as a staged research and modelling project for battery energy optimisation across residential, distributed, and grid-scale use cases.

## Phase 1 - Residential Energy Optimisation

**Current status:** partially implemented.

**Scope:**

- Solar generation
- Household load
- Home battery
- Tariff optimisation
- Residential arbitrage
- EV charging integration

**Existing modules:**

- `src/solar_load_model.py`
- `src/solar_backtest.py`
- `src/tariff_scenarios.py`
- `src/battery_model.py`
- `src/strategy.py`
- `src/backtest.py`
- `src/performance.py`

**Limitations:**

- Solar and load profiles are simplified and not yet calibrated against site-specific metering data.
- Residential dispatch is mostly rule-based rather than optimisation-based.
- Tariff modelling is scenario-oriented and does not yet cover all retail tariff structures.
- Battery degradation is simplified and primarily throughput-based.
- EV charging is not yet represented as a first-class controllable load.

**Possible future work:**

- Add interval-level household consumption import and validation.
- Implement optimisation-based dispatch for time-of-use tariffs, feed-in tariffs, and dynamic price signals.
- Model EV charging as a flexible load with arrival time, departure time, required energy, and charger limits.
- Add calendar ageing, cycle ageing, depth-of-discharge effects, and capacity fade.
- Compare household bill savings, self-consumption, arbitrage revenue, and battery wear across tariff regimes.

## Phase 2 - Distributed Energy Systems

**Current status:** conceptual / not yet implemented.

**Scope:**

- VPP concepts
- Aggregated residential batteries
- Demand response
- Dynamic tariffs
- Grid interaction

**Existing modules:**

- No dedicated VPP or aggregation modules.
- Phase 1 residential battery, tariff, and load models provide possible component models.

**Limitations:**

- No aggregation layer for multiple households or distributed batteries.
- No representation of portfolio diversity, availability, customer opt-out, or telemetry latency.
- No network constraint model for feeders, export limits, voltage constraints, or local congestion.
- Dynamic tariffs and demand response events are not modelled as dispatch signals.
- Grid interaction is indirect and currently limited to price-responsive residential behaviour.

**Possible future work:**

- Add a VPP portfolio model composed of heterogeneous household batteries, solar systems, loads, and EVs.
- Implement demand response events with customer availability, rebound effects, and dispatch compliance.
- Add dynamic tariff support and compare household-level versus aggregator-level optimisation.
- Model export limits, feeder constraints, and local network capacity.
- Track aggregator revenue, customer bill impacts, and operational constraint violations separately.

## Phase 3 - Grid-Scale Battery Markets

**Current status:** partially implemented.

**Scope:**

- Wholesale arbitrage
- FCAS participation
- Stacked revenues
- Reserve constraints
- Dispatch optimisation

**Existing modules:**

- `src/fcas_simulator.py`
- `src/nemosis_loader.py`
- `src/aemo_downloader.py`
- `src/price_feed.py`
- `src/live_runner.py`
- `src/decision_engine.py`
- `src/config.py`

**Limitations:**

- Wholesale arbitrage uses simplified threshold logic rather than co-optimised dispatch.
- FCAS is represented as a simplified availability service, not separate raise/lower regulation and contingency products.
- FCAS prices, enablement, activation, and settlement are not fully modelled from historical market data.
- Reserve constraints are simplified and do not yet reflect bidirectional service requirements in detail.
- No bidding, rebidding, dispatch targets, loss factors, constraints, outages, or settlement-grade interval ledger.

**Possible future work:**

- Implement optimisation-based wholesale arbitrage over rolling forecast horizons.
- Add separate FCAS products with direction, enablement, activation, and opportunity cost accounting.
- Model stacked revenue strategies with explicit energy, power, and SoC reservation constraints.
- Add NEM dispatch interval replay for price-taking battery operation.
- Compare threshold, perfect-foresight, and forecast-based dispatch strategies.

## Phase 4 - Market Simulation & Research

**Current status:** early research direction.

**Scope:**

- Historical NEM replay
- Market regime analysis
- Battery saturation effects
- Degradation economics
- Stochastic modelling
- Live market integration

**Existing modules:**

- `src/nemosis_loader.py`
- `src/aemo_downloader.py`
- `src/price_feed.py`
- `src/live_runner.py`
- Existing backtest, performance, and FCAS simulation modules may be reused.

**Limitations:**

- Historical replay is limited to available price data and simplified dispatch assumptions.
- No explicit market regime classifier for volatility, negative prices, scarcity events, or renewable penetration.
- Battery saturation and price-impact effects are not modelled.
- Stochastic inputs for prices, solar, load, outages, and activation events are not yet implemented.
- Live market integration is not yet connected to a production-grade control loop or persistence layer.

**Possible future work:**

- Build historical NEM replay pipelines across regions, years, and market regimes.
- Add regime analysis for negative price frequency, evening scarcity, volatility clustering, and FCAS price events.
- Simulate battery fleet saturation and resulting arbitrage spread compression.
- Extend degradation economics to include replacement cost, warranty constraints, and cycle-depth sensitivity.
- Add stochastic price and load scenarios for risk-adjusted revenue analysis.
- Develop live data ingestion, interval logging, monitoring, and comparison against simulated dispatch.
