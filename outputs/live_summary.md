# Live Observation Summary

Analytical report generated from `outputs/live_observation.csv`.

## Summary Statistics

- Total intervals observed: 109
- EXPORT actions: 32
- HOLD actions: 77
- Average spike price: $0.2707/kWh
- Highest observed price: $0.2979/kWh
- Total simulated cashflow: $2.8939
- Average SoC: 38.11%
- Minimum SoC reached: 20.00%
- Longest spike cluster: 3 intervals
- Percentage of exports occurring during price_spike: 100.0%

## Regime Frequencies

| Regime | Count | Share |
| --- | ---: | ---: |
| normal | 46 | 42.2% |
| price_spike | 34 | 31.2% |
| sustained_high_price_event | 16 | 14.7% |
| volatile | 13 | 11.9% |

## Findings

- Exports remained concentrated in spike regimes (100.0% during price_spike).
- SoC exhaustion occurred: minimum simulated SoC reached 20.00%.
- Normal periods did not generate meaningful activity (0 active intervals, $0.0000 simulated cashflow).
