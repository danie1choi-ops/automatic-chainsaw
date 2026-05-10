# Live Observation Mode

`live-observe` runs the project in monitoring and paper-dispatch mode only. It reads a current QLD price feed, classifies the observed market regime, applies the current dispatch logic to a simulated battery, and appends the result to a CSV log.

It does not connect to hardware and does not send battery commands.

## Usage

```bash
python3 -m src.main --mode live-observe
```

By default, the command uses the mock price feed and polls every 300 seconds, matching the configured 5-minute interval length.

To request a specific feed:

```bash
python3 -m src.main --mode live-observe --feed aemo
```

If the requested live feed is unavailable, observation mode falls back to the mock feed and continues running.

The polling interval can be changed for testing:

```bash
python3 -m src.main --mode live-observe --poll-seconds 5
```

## Output

Observations are appended to:

```text
outputs/live_observation.csv
```

Columns:

- `timestamp`: feed timestamp in ISO format
- `price`: observed price in $/kWh
- `regime`: classified market regime
- `action`: simulated dispatch action (`CHARGE`, `HOLD`, or `EXPORT`)
- `simulated_soc`: simulated battery state of charge after the paper action
- `simulated_cashflow`: simulated interval cashflow after degradation cost
- `reason`: strategy reason for the simulated action

## Dispatch Scope

The mode reuses the current rule-based strategy and battery model:

- charge when price is at or below the configured charge threshold and simulated SoC allows it
- export when price is at or above the configured export threshold and simulated SoC allows it
- otherwise hold

Cashflow is simulated only. Charge actions are treated as energy cost, export actions as revenue, and degradation is deducted using the configured per-kWh degradation cost.

## Regime Classification

Live classification uses fixed $/kWh thresholds plus rolling volatility from the current observation session:

- negative pricing: price below zero
- price spike: price at or above the configured export threshold
- sustained high-price event: price remains above the live high-price threshold for the configured number of intervals
- volatile: rolling price volatility exceeds the live volatility threshold
- normal: none of the above

This differs from historical regime studies, which can resolve percentile thresholds from a complete price series. The live mode avoids percentile classification on a single current price point.

## Limitations

- Live AEMO and Amber feeds are placeholders unless implemented separately.
- The fallback mock feed is useful for continuity and testing, not for market conclusions.
- Simulated SoC starts from the configured initial SoC at process start and is not synchronised to a physical battery.
- The dispatch model remains threshold-based and is not an optimiser.
- No FCAS price integration is used in this mode.
- This is monitoring and research infrastructure only, not investment advice.
