# Saturation Simulator

`src/saturation_simulator.py` models how increasing battery participation can compress volatility-driven arbitrage profits. It is an analytical sensitivity tool, not a market simulator.

## Purpose

The module tests whether profitability is structurally dependent on scarce volatility events. It starts from realised interval results and applies explicit assumptions about participation pressure:

- multiple batteries reacting to the same volatility regimes
- reduced spread capture
- dampened spike value
- competition for export windows
- changed degradation contribution as export opportunities compress

## Assumptions

The simulator does not model bidding, dispatch targets, network constraints, price formation, rebidding, or market clearing.

For affected regimes, defaulting to `volatile`, `price_spike`, and `sustained_high_price_event`:

- spread compression increases with `number_batteries - 1`
- compression scales with `reaction_aggressiveness`
- compression scales with `spread_compression_factor`
- export-window availability declines through `export_window_competition_factor`
- per-battery degradation scales with adjusted throughput

Normal and negative-price intervals are not compressed by default unless included in `affected_regimes`.

## API

- `simulate_saturation()`: simulate one participation level.
- `compare_participation_levels()`: compare multiple participation levels and return a profit decay curve.
- `profitability_decay_vs_participation()`: return only the curve output for charting or CSV export.

Configuration is provided by `SaturationConfig`:

- `number_batteries`
- `battery_size`
- `reaction_aggressiveness`
- `spread_compression_factor`
- `export_window_competition_factor`
- `degradation_cost_per_energy`
- `affected_regimes`

## Outputs

`simulate_saturation()` returns:

- single-battery baseline profitability
- per-battery saturated profitability
- fleet profitability
- profit decay
- volatility compression
- export-window competition
- per-battery and fleet degradation
- adjusted interval rows
- regime profitability after saturation

`compare_participation_levels()` returns:

- profit decay curves
- volatility compression by participation level
- degradation impact by participation level
- regime profitability changes for each scenario

## Interpretation

This module is useful for stress-testing conclusions such as:

- price spikes dominate profits only when participation is low
- more batteries reduce spread capture per battery
- fleet profit can rise while per-battery profit falls
- normal-period degradation can remain a drag even when spike revenue is compressed

The outputs should be read as sensitivity analysis, not forecasts.
