# Regime Profitability Analysis

`src/regime_profitability_analysis.py` analyses realised battery profitability by market regime. It joins classified market intervals with existing dispatch or backtest results and aggregates P&L drivers by regime.

## Purpose

The module is designed to answer whether battery arbitrage revenue is concentrated in specific market conditions, such as negative prices, volatility, price spikes, or sustained high-price events.

It is analytical only:

- no strategy optimisation
- no dispatch decisions
- no bidding logic
- no market simulation

## Inputs

The main input is an interval-level dispatch result series. Rows may be dictionaries or objects with common fields such as:

- price: `price`, `price_per_kwh`, `price_per_mwh`, `RRP`, `rrp`
- profit: `profit`, `cashflow`, `net_cashflow`, `arbitrage_profit`, `net_revenue`
- export energy: `energy_exported`, `exported_energy`, `exported_kwh`, `exported_mwh`, `battery_discharged_arbitrage`
- charge energy: `energy_charged`, `charged_energy`, `charged_kwh`, `charged_mwh`, `battery_charged_arbitrage`
- degradation: `degradation_cost`, `degradation`, `degradation_contribution`
- spread: `spread_captured`, `captured_spread`, `arbitrage_spread`

Regimes can be supplied explicitly as strings, `RegimeInterval` objects, or dictionaries with a `regime` field. If regimes are not supplied, the module classifies rows using `src/regime_analysis.py`.

## API

- `profitability_by_regime()`: returns full profitability metrics and regime rankings.
- `cycles_by_regime()`: returns cycle contribution by regime.
- `export_activity_by_regime()`: returns exported energy and export interval counts by regime.
- `degradation_by_regime()`: returns degradation contribution and degradation dominance flags.

`RegimeProfitabilityConfig` can provide fallback assumptions when interval rows do not contain all fields:

- battery capacity for cycle contribution estimates
- degradation cost per unit of energy throughput
- explicit field-name overrides

## Outputs

For each regime, `profitability_by_regime()` returns:

- average profit
- total profit
- average spread captured
- energy exported
- export interval count
- cycle contribution
- degradation contribution
- percentage of total profitability
- whether the regime is profitable
- whether degradation dominates realised profit
- average price

The summary also identifies:

- regimes where arbitrage is profitable
- regimes where degradation dominates
- regimes contributing most absolute P&L

## Notes

Average spread captured uses an explicit spread field when available. If no explicit spread is present, it estimates spread from realised export prices minus realised charge prices within the same regime. If the data does not contain both charge and export prices for a regime, the spread is reported as `None`.

Cycle contribution uses explicit cycle fields when available. Otherwise, it can estimate cycles from energy throughput if `battery_capacity_energy` is supplied.

The module is intentionally generic so it can later consume FCAS simulator interval rows or stacked-revenue outputs without embedding FCAS-specific dispatch logic.
