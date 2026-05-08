# Timestamp Alignment

The regime profitability research pipeline must align backtest intervals to historical market price intervals before classification. Regime attribution must use the aligned market price, not the price embedded in a backtest output row.

## Standardisation

`src/timestamp_alignment.py` applies the following steps:

- parse timestamps using ISO-compatible formats, including space-separated and `T`-separated strings
- handle timezone-aware timestamps by converting them to the configured local timezone
- treat timezone-naive timestamps as already local to the configured timezone
- round timestamps to the configured interval length
- format aligned timestamps consistently as ISO strings without timezone suffixes

Default settings:

- timezone: `Australia/Brisbane`
- interval length: 5 minutes
- rounding: nearest interval
- minimum match ratio: 100%

## API

- `standardise_timestamp()`: parse, timezone-normalise, round, and return a naive local interval timestamp.
- `timestamp_alignment_report()`: compare historical market rows and backtest rows and return match diagnostics.
- `align_market_prices()`: attach aligned historical market prices to backtest rows as `regime_price`.

`align_market_prices()` raises `ValueError` when the matched interval share is below the configured minimum. This prevents silent fallback to embedded backtest prices.

## Diagnostics

The alignment report includes:

- total historical price rows
- total backtest rows
- matched rows
- matched interval percentage
- missing market interval count
- unused market interval count
- duplicate market timestamps
- duplicate backtest timestamps
- sampled unmatched backtest timestamps
- sampled missing market intervals
- market and backtest time ranges

The research runner writes:

- `research/output/timestamp_alignment_report.md`
- `research/output/timestamp_alignment_diagnostics.csv`

## Research Pipeline Contract

`research/run_regime_study.py` now performs timestamp alignment before regime classification. If intervals do not align, it writes diagnostics and stops. It does not classify regimes from embedded backtest prices.

To produce a valid regime profitability study, regenerate or provide `outputs/backtest_results.csv` for the same historical interval range as the selected market price CSV.
