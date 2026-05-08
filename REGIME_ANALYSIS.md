# Regime Analysis

`src/regime_analysis.py` classifies historical price intervals into market regimes so battery revenue can be analysed against actual market conditions rather than an assumed uniform price process.

## Regimes

- `normal`: default condition when no other rule applies.
- `volatile`: rolling price volatility exceeds the configured volatility threshold.
- `negative_pricing`: interval price is below the configured negative price threshold.
- `price_spike`: interval price is above the configured spike threshold.
- `sustained_high_price_event`: price remains above the high-price threshold for the configured number of consecutive intervals.

Classification priority is:

1. Negative pricing
2. Price spike
3. Sustained high-price event
4. Volatile
5. Normal

## Configuration

`RegimeAnalysisConfig` supports:

- percentile thresholds for high-price, spike, and rolling volatility classification
- explicit threshold overrides when fixed values are preferred
- rolling volatility window length
- consecutive interval count for sustained high-price events
- interval duration for average duration calculations

Threshold units must match input price units. For example, use `$/MWh` thresholds for raw NEM RRP data and `$/kWh` thresholds for converted retail-style data.

## API

- `classify_interval()`: classifies one interval using a price and precomputed context such as rolling volatility and consecutive high-price count.
- `classify_day()`: classifies a daily series and returns the dominant regime, regime frequency, average price by regime, and classified intervals.
- `summarise_regimes()`: classifies a full series and returns frequency, average duration, average price by regime, transition statistics, resolved thresholds, and classified intervals.

Inputs may be numeric price sequences, dictionaries, or objects with common fields such as `price`, `RRP`, `price_per_mwh`, `price_per_kwh`, and `timestamp`.

## Outputs

`summarise_regimes()` returns:

- frequency of each regime as count and share
- average duration in hours for each regime
- average price by regime
- transition counts and transition probabilities
- interval-level classifications for downstream analysis
- resolved percentile or fixed thresholds used in the run

## Intended Use

This module is analytical only. It does not dispatch batteries, optimise bids, or create trading signals. The intended workflow is to classify historical price data first, then compare modelled battery revenues across regime types to identify when revenue is concentrated in negative prices, volatility, spikes, or sustained high-price periods.
