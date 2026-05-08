# Research Studies

This directory contains reproducible analytical studies built on existing repository modules. Studies should not add dispatch logic, strategy optimisation, or trading rules.

## Regime Profitability Study

Run:

```bash
python3 research/run_regime_study.py
```

Default inputs:

- historical prices: `data/qld_prices_6m.csv`
- backtest results: `outputs/backtest_results.csv`
- output directory: `research/output/`

Optional inputs:

```bash
python3 research/run_regime_study.py \
  --prices data/qld_prices_6m.csv \
  --backtest outputs/backtest_results.csv \
  --output-dir research/output
```

The runner attempts to align historical prices and backtest rows by timestamp. If no timestamp match is available, it classifies regimes using the price embedded in the backtest results and records that limitation in the report.

By default, high-price and spike thresholds use the repository arbitrage configuration in the same units as the input prices. Percentile thresholds are still configurable and are used when fixed thresholds are omitted in custom code or future variants.

## Outputs

The study writes:

- `timestamp_alignment_report.md`
- `timestamp_alignment_diagnostics.csv`
- `profitability_by_regime.csv`
- `cycles_by_regime.csv`
- `export_activity_by_regime.csv`
- `degradation_by_regime.csv`
- `regime_classifications.csv`
- `cumulative_pnl_by_regime.csv`
- `regime_study_report.md`
- `profit_contribution_by_regime.svg`
- `duration_vs_profitability.svg`
- `degradation_vs_revenue.svg`
- `cumulative_pnl_by_regime.svg`

## Questions Addressed

- Which regimes dominate profitability?
- Is profitability concentrated in rare price spikes?
- Does degradation outweigh value in normal periods?
- Is battery value structurally dependent on volatility?

## Constraints

- Analytical only
- Uses existing regime and profitability attribution modules
- No new strategy logic
- No new dispatch logic
- Reusable with future FCAS simulator interval outputs
- Regime attribution uses aligned historical market prices only
