# Solar Generation and Load Modelling

## Overview

The solar generation and household load modelling system adds realistic daily solar generation profiles and household electricity demand patterns to the energy arbitrage simulator. This enables measurement of:

1. **Grid import cost reduction** from solar generation
2. **Incremental arbitrage benefit** on top of solar + load management

## Architecture

### Two New Modules

#### `src/solar_load_model.py`
- **SolarProfile**: Defines daily solar generation curve (bell curve model)
- **HouseholdLoad**: Defines daily household electricity demand
- Helper functions for calculating energy per interval

#### `src/solar_backtest.py`
- **run_solar_backtest()**: Main backtest engine with solar + load + arbitrage
- Energy flow logic: Solar → Battery → Load/Export
- Economic analysis: Grid cost savings + arbitrage profit
- **SolarLoadResults**: Structured results with metrics

## Solar Generation Model

### Bell Curve Profile

Solar generation follows a bell curve (normal distribution) with configurable parameters:

```python
from src.solar_load_model import SolarProfile

solar_profile = SolarProfile(
    peak_hour=12.0,        # Noon
    peak_power_kw=8.0,     # 8 kW system (typical rooftop)
    sunrise_hour=6.0,      # 6 AM
    sunset_hour=18.0,      # 6 PM
)
```

**Formula**: Power(t) = peak_power × exp(-0.5 × ((t - peak_hour) / σ)²)

Where σ (standard deviation) spans from sunrise to sunset.

### Default Profile

```python
DEFAULT_SOLAR_PROFILE = SolarProfile(
    peak_hour=12.0,
    peak_power_kw=8.0,      # 8 kW peak (typical install)
    sunrise_hour=6.0,
    sunset_hour=18.0,
)
```

Generates approximately 40-50 kWh on a typical sunny day.

## Household Load Model

### Hourly Profile with Interpolation

Household loads interpolate between hourly values:

```python
DEFAULT_HOUSEHOLD_LOAD = HouseholdLoad(
    hourly_profile={
        0: 0.3,    # Midnight: 300W baseline
        6: 0.8,    # 6 AM: 800W morning activity
        12: 0.6,   # Noon: 600W
        18: 2.0,   # 6 PM: 2000W peak evening
        # ... etc for all 24 hours
    }
)
```

Typically generates 15-25 kWh of demand per day.

### Default Profile

Typical Australian household:
- **Night (midnight-6am)**: 300-400W baseline
- **Morning (6-9am)**: 800-1200W peak
- **Midday (9-18)**: 500-900W (lower with solar)
- **Evening (18-22)**: 1200-2000W peak
- **Late night (22-0)**: 500-800W

## Energy Flow Logic

For each 5-minute interval:

```
1. Solar Generation
   ↓
2. Solar → Battery (up to capacity)
3. Remaining Solar → Grid (export)
   ↓
4. Household Demand
   ↓
5. Demand → Battery (discharge)
6. Remaining Demand → Grid (import)
   ↓
7. Arbitrage Strategy (if battery space)
   - CHARGE if price is low
   - EXPORT if price is high
```

### Key Points

- Solar feeds into battery **first** (prioritized)
- Excess solar is **exported** to grid
- Household load consumes from battery **before grid**
- Arbitrage logic applies to remaining battery capacity
- All flows tracked separately for analysis

## Economic Measurements

### Grid Import Cost (Without Solar)

```
Cost = Total Household Demand × Import Price
```

Example: 19 kWh × $0.30/kWh = $5.70

### Grid Import Cost (With Solar)

```
Cost = Remaining Grid Import × Import Price
```

Example: 7.21 kWh × $0.30/kWh = $2.16

### Solar Savings

```
Savings = Cost (without solar) - Cost (with solar)
        = $5.70 - $2.16 = $3.54
```

Represents cost avoided by having solar.

### Arbitrage Profit On Top

Remaining battery capacity used for price arbitrage:
- Profit = Revenue from arbitrage - Degradation cost

Example: $89.58 (based on price spreads)

### Total Benefit

```
Total Benefit = Solar Savings + Arbitrage Profit
              = $3.54 + $89.58 = $93.12
```

Combined economic benefit from solar + arbitrage.

## Usage

### Command Line

```bash
# Run solar backtest with default parameters (8kW solar, $0.30 import)
python3 -m src.main --mode backtest --file data/sample_prices.csv --solar

# Run with custom solar power
python3 -m src.main --mode backtest --file data/sample_prices.csv --solar \
  --solar-peak-kw 5.0

# Run with custom import price
python3 -m src.main --mode backtest --file data/sample_prices.csv --solar \
  --import-price 0.35

# Both custom parameters
python3 -m src.main --mode backtest --file data/sample_prices.csv --solar \
  --solar-peak-kw 10.0 --import-price 0.40
```

### Python API

```python
from src.solar_backtest import run_solar_backtest
from src.solar_load_model import SolarProfile, HouseholdLoad
from src.data_loader import load_price_data

# Create custom profiles
solar = SolarProfile(
    peak_hour=13.0,
    peak_power_kw=10.0,
    sunrise_hour=5.30,
    sunset_hour=19.30,
)

load = HouseholdLoad(
    hourly_profile={
        0: 0.2, 6: 1.0, 12: 0.5, 18: 2.5, # ... etc
    }
)

# Load price data
price_data = load_price_data('data/prices.csv')

# Run backtest
backtest_results, solar_load_results = run_solar_backtest(
    price_data,
    solar_profile=solar,
    household_load=load,
    import_price_per_kwh=0.35,
)

# Print results
print(solar_load_results)
```

## Output

### Console Output

```
SOLAR BACKTEST RESULTS
======================================================================
Total Intervals:              288
Total Solar Generated:        57.51 kWh
Total Household Demand:       19.00 kWh
Total Grid Import:            7.21 kWh
Total Solar Self-Consumed:    46.43 kWh
Total Solar Exported:         11.08 kWh
----------------------------------------------------------------------
Grid Cost (no solar):         $5.70
Grid Cost (with solar):       $2.16
Solar Savings:                $3.54
Arbitrage Profit:             $89.58
Total Benefit:                $93.12
Ending SoC:                   20.0%
======================================================================
```

### Structured Results

```python
solar_load_results = SolarLoadResults(
    total_solar_generated_kwh=57.51,
    total_household_demand_kwh=19.00,
    total_grid_import_kwh=7.21,
    total_solar_self_consumed_kwh=46.43,
    total_solar_exported_kwh=11.08,
    total_battery_charged_from_solar_kwh=46.43,
    total_battery_discharged_to_load_kwh=11.79,
    total_battery_discharged_to_export_kwh=45.87,
    grid_import_cost_without_solar=5.70,
    grid_import_cost_with_solar=2.16,
    solar_savings=3.54,
    arbitrage_profit_on_top=89.58,
    total_benefit=93.12,
)
```

## Interpretation Guide

### Solar Payback Estimation

Annual solar benefit:
```
Annual = Period Benefit × (365 / period_days)
       = $3.54 × (365 / 1) = $1,291/year
```

Simple payback (assuming $8,000 system cost):
```
Payback = $8,000 / $1,291 = 6.2 years
```

Plus arbitrage profit:
```
Total Annual = $1,291 + annual_arbitrage
             = Higher ROI
```

### Key Metrics

| Metric | Indicates |
|--------|-----------|
| **Solar Self-Consumption %** | How much solar is used locally vs exported |
| **Grid Import Reduction** | Effectiveness of solar + storage |
| **Arbitrage Profit** | Value added by battery trading |
| **Total Benefit** | Combined economic benefit |

### When Solar Is Most Valuable

1. **High import tariff** ($0.30+/kWh retail)
2. **Low export tariff** ($0.10-0.15/kWh feed-in)
3. **Aligned solar + demand** (use during generation)
4. **High price volatility** (arbitrage opportunities)

## Configuration

Customize in `src/config.py`:

```python
# Time intervals
INTERVAL_MINUTES = 5  # Price data interval

# Battery configuration
BATTERY_CAPACITY_KWH = 13.5
MAX_CHARGE_KW = 5.0
MAX_DISCHARGE_KW = 5.0
```

## Design Principles

✅ **Solar prioritized**: Feeds into battery before grid import  
✅ **Load prioritized**: Consumed from battery before grid  
✅ **Trading preserved**: Arbitrage applies to remaining capacity  
✅ **Clear tracking**: All flows recorded separately  
✅ **Economic clarity**: Separates solar benefit from arbitrage profit  

## Testing

Run tests:

```bash
# Solar and load model tests
python3 -m pytest tests/test_solar_load_model.py -v

# Solar backtest tests
python3 -m pytest tests/test_solar_backtest.py -v

# All tests
python3 -m pytest tests/ -v
```

## Assumptions

- **Daily profile repeats**: Same solar + load each day
- **No seasonal variation**: Fixed profiles (could be enhanced)
- **Linear interpolation**: Load between hourly values
- **Bell curve solar**: Symmetrical generation around peak
- **No weather variation**: Constant generation (sunny day)
- **Perfect efficiency**: No system losses

## Future Enhancements

1. **Seasonal profiles**: Different profiles for summer/winter
2. **Weather-based variation**: Cloudy day reduction
3. **Export revenue**: Track feed-in credits
4. **Multi-day analysis**: Extend beyond daily patterns
5. **Custom tariff schedules**: Time-of-use pricing
6. **Household solar sizing**: Optimize system size
