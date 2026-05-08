# Saturation Study

`research/run_saturation_study.py` runs a battery participation sensitivity study using the historical regime attribution output from `research/run_regime_study.py`.

## Purpose

The study asks how much of the observed arbitrage value depends on scarce volatility windows. It applies explicit saturation assumptions to realised regime profitability and measures per-battery and fleet economics as participation increases.

## Inputs

Default input:

- `research/output/regime_classifications.csv`

This file must be produced by the regime study and must contain aligned market prices. The saturation study does not run dispatch logic and does not reclassify regimes.

## Participation Levels

The default study simulates:

- 1 battery
- 10 batteries
- 100 batteries
- 1,000 batteries
- 10,000 batteries

## Assumptions

The study uses `src/saturation_simulator.py`.

Default assumptions:

- battery size: repository battery capacity
- reaction aggressiveness: `1.0`
- spread compression factor: `0.05`
- export-window competition factor: `0.02`
- degradation cost per energy: repository degradation cost
- affected regimes: `volatile`, `price_spike`, `sustained_high_price_event`

These are sensitivity assumptions only. The study does not model bidding, dispatch targets, network constraints, market clearing, or price formation.

## Outputs

Saved to `research/output/saturation/`:

- `saturation_profit_curve.csv`
- `saturation_regime_profitability.csv`
- `saturation_regime_frequencies.csv`
- `saturation_assumptions.csv`
- `saturation_study_report.md`
- `profit_vs_participation.svg`
- `spike_profitability_decay.svg`
- `regime_contribution_changes.svg`
- `volatility_compression.svg`

## Run

```bash
python3 research/run_saturation_study.py
```

Optional:

```bash
python3 research/run_saturation_study.py \
  --regime-classifications research/output/regime_classifications.csv \
  --spread-compression-factor 0.05 \
  --export-window-competition-factor 0.02 \
  --reaction-aggressiveness 1.0
```

## Interpretation

The report highlights:

- when per-battery profitability materially collapses
- whether spikes remain monetisable
- whether degradation dominates after saturation
- implications for residential and grid-scale systems

Outputs should be read as analytical stress tests, not forecasts.
