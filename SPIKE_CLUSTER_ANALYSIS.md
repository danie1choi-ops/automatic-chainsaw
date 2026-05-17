# Spike Cluster Analysis

`src/spike_cluster_analysis.py` is an analysis-only module for measuring whether
the simulated battery exhausts SoC too early during clustered price spikes. It
does not change strategy logic, dispatch rules, or hardware-control behaviour.

## Inputs

The module can analyse in-memory rows or existing CSV outputs:

- `outputs/backtest_results.csv`
- `outputs/live_observation.csv`

It recognises both current schemas:

- Backtest: `timestamp`, `price_per_kwh`, `action`, `soc_percent`,
  `energy_kwh`, `cashflow`
- Live observation: `timestamp`, `price`, `regime`, `action`,
  `simulated_soc`, `simulated_cashflow`

If a `regime` field is present, rows with `regime == "price_spike"` are treated
as spike intervals. Otherwise, spikes are inferred from
`spike_price_threshold`, which defaults to `config.EXPORT_PRICE_THRESHOLD`.

## Cluster Detection

`SpikeClusterAnalysisConfig` controls detection:

- `max_gap_intervals`: allowed non-spike intervals between spike intervals in
  the same cluster
- `min_cluster_size`: minimum spike intervals required for a cluster
- `spike_price_threshold`: fallback price threshold when no regime column exists

This captures consecutive and near-consecutive spikes without requiring the
strategy itself to know about clusters.

## Cluster Metrics

Each `SpikeCluster` reports:

- start and end timestamp
- number of spike intervals
- max price and average spike price
- first and last export timestamp
- starting and ending SoC
- number of exports
- missed spike exports due to `MIN_SOC`
- realised cashflow
- theoretical cashflow if energy had been reserved

Starting SoC is estimated from the first spike row. If that first row exported
and `energy_kwh` is available, the module adds the exported energy back to the
post-dispatch SoC to approximate pre-spike SoC.

Theoretical reserved cashflow assumes the cluster-start usable energy above
`MIN_SOC` was reserved for spike intervals, then exported subject to
`MAX_DISCHARGE_KW`, interval duration, and degradation cost. It is a diagnostic
estimate, not an optimisation or dispatch instruction.

## Summary

`summarise_spike_clusters()` returns:

- `total_clusters`
- `average_cluster_duration_hours`
- `average_soc_drawdown`
- `missed_spike_count`
- `estimated_missed_cashflow`
- `percentage_clusters_ending_at_min_soc`

`estimated_missed_cashflow` is calculated as the positive difference between
the reserved-energy theoretical cashflow and realised cluster cashflow.

## Example

```python
from src.spike_cluster_analysis import (
    SpikeClusterAnalysisConfig,
    analyse_spike_clusters,
    load_default_output_rows,
    summarise_spike_clusters,
)

rows = load_default_output_rows()
cfg = SpikeClusterAnalysisConfig(max_gap_intervals=1, min_cluster_size=2)

clusters = analyse_spike_clusters(rows, cfg)
summary = summarise_spike_clusters(clusters, cfg)
```

The output is intended for research and validation reports. It should be used to
decide whether strategy changes are worth investigating, not to perform dispatch.
