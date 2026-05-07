# Tariff Scenario Modelling

## Overview

The tariff scenario module provides economic analysis across four different operating modes for battery energy arbitrage. Each scenario models a distinct business case with different import/export tariffs and capital cost assumptions.

## Four Standard Scenarios

### 1. Wholesale Arbitrage Mode
**Profile**: Commercial/wholesale market participant
- **Import Price**: $0.10/kWh (typical wholesale buy)
- **Export Price**: $0.15/kWh (typical wholesale sell)
- **Capital Cost**: Full system cost ($17,000)
- **Use Case**: Energy trader or commercial facility with AEMO market access
- **Advantages**: Best price spreads, optimal for maximizing arbitrage margins
- **Constraints**: Requires market participation capability

### 2. Retail Import/Feed-in Tariff Mode
**Profile**: Household with solar but relying on grid
- **Import Price**: $0.35/kWh (typical retail import tariff)
- **Export Price**: $0.12/kWh (typical feed-in tariff)
- **Capital Cost**: Full system cost ($17,000)
- **Use Case**: Household battery with limited solar generation
- **Advantages**: Realistic for residential customers
- **Constraints**: Narrow or even negative margins; may not justify battery investment

### 3. Existing Battery Marginal Mode
**Profile**: Already owns battery; optimizing operations
- **Import Price**: $0.25/kWh (mid-range retail)
- **Export Price**: $0.15/kWh (better feed-in or market access)
- **Capital Cost**: $0 (already owned, consider sunk)
- **Use Case**: Deciding whether to continue operating an existing battery
- **Advantages**: Only considers marginal (degradation) costs
- **Constraints**: Decision to operate, not to buy

### 4. New Battery Full-Cost Mode
**Profile**: Evaluating battery purchase for new installation
- **Import Price**: $0.30/kWh (moderate retail)
- **Export Price**: $0.18/kWh (good export opportunity)
- **Capital Cost**: Full system cost ($17,000)
- **Use Case**: Household or small commercial evaluating battery ROI
- **Advantages**: Realistic full-cost scenario
- **Constraints**: Must recover full capital + operating costs

## Economic Metrics

Each scenario calculates four key profit metrics:

### Gross Profit
Total revenue from arbitrage trading (buying low, selling high) before degradation costs.
- Formula: Sum of (energy_discharged × export_price) - (energy_charged × import_price)
- Interpretation: Raw trading revenue, doesn't account for battery wear

### Degradation Cost
Cost of battery wear from charging/discharging cycles.
- Formula: (total_energy_moved) × $0.05/kWh
- Interpretation: Total battery lifecycle cost consumed
- Configuration: `config.DEGRADATION_COST_PER_KWH`

### Net Marginal Profit
Economic profit after degradation costs.
- Formula: Gross Profit - Degradation Cost
- Interpretation: Profit available for capital cost recovery
- Key metric for investment decision

### Annualised Profit
Net marginal profit extrapolated to a full year.
- Formula: Net Marginal Profit × (365 / period_days)
- Interpretation: Expected annual profit if conditions persist
- Basis for payback analysis

### Simple Payback (years)
Years to recover initial investment from annual profits.
- Formula: Battery System Cost / Annualised Profit
- Interpretation: ROI timeframe
- `Never` if annualised profit ≤ $0

## Usage

### Run Scenario Analysis from Command Line

```bash
# Basic scenario analysis
python3 -m src.main --mode backtest --file data/sample_prices.csv --scenarios

# Save results to CSV
python3 -m src.main --mode backtest --file data/sample_prices.csv --scenarios \
  --scenario-output outputs/scenario_results.csv
```

### Run Scenarios Programmatically

```python
from src.tariff_scenarios import (
    TARIFF_SCENARIOS,
    run_scenario,
    run_all_scenarios,
    print_scenario_summary,
    export_scenario_results_csv,
)
from src.data_loader import load_price_data

# Load price data
price_data = load_price_data('data/sample_prices.csv')

# Run all scenarios
results = run_all_scenarios(price_data)

# Print summary
print_scenario_summary(results)

# Export to CSV
export_scenario_results_csv(results, 'outputs/scenarios.csv')

# Or run individual scenario
scenario = TARIFF_SCENARIOS[0]  # Wholesale mode
result = run_scenario(scenario, price_data)
print(f"Annual profit: ${result.annualised_profit:.2f}")
```

### Custom Scenarios

Create custom tariff scenarios for specific use cases:

```python
from src.tariff_scenarios import TariffScenario, run_scenario
from src.data_loader import load_price_data

# Define custom scenario
my_scenario = TariffScenario(
    name="My Custom Scenario",
    description="Custom tariff structure",
    import_price_per_kwh=0.28,
    export_price_per_kwh=0.16,
    charge_threshold=0.28,
    export_threshold=0.16,
    system_cost_override=17000,  # or None to use config default
)

# Run it
price_data = load_price_data('data/sample_prices.csv')
result = run_scenario(my_scenario, price_data)
print(result)
```

## Output Format

### Console Output

Each scenario displays:
```
Scenario Name
----------------------------------------------------------------------
  Description...
  
  Import Price:      $X.XXXX/kWh
  Export Price:      $X.XXXX/kWh
  
  Period Performance:
    Gross Profit:       $      X.XX
    Degradation Cost:   $      X.XX
    Net Marginal Profit:$      X.XX
    
  Operating Metrics:
    Charged Energy:           X.XX kWh
    Exported Energy:          X.XX kWh
    Equivalent Cycles:        X.XX cycles
    Export Actions:             XX times
    
  Period Analysis:
    Period Duration:           X.X days
    Annualised Profit:  $      X.XX/year
    
  Investment Analysis:
    Simple Payback:         X.X years
    Ending SoC:              X.X%
```

### CSV Output

CSV format with columns:
- Scenario
- Import Price ($/kWh)
- Export Price ($/kWh)
- Gross Profit ($)
- Degradation Cost ($)
- Net Marginal Profit ($)
- Period Days
- Annualised Profit ($/year)
- Simple Payback (years) - blank if never
- Charged Energy (kWh)
- Exported Energy (kWh)
- Equivalent Cycles
- Export Actions

## Interpretation Guide

### When to Consider a Scenario Viable

**Wholesale Mode**: Annual profit > $1,000 (payback < 17 years)
**Retail Mode**: Annual profit > $500 (often not viable)
**Marginal Mode**: Any positive net profit justifies operation
**New Battery**: Annual profit > $2,000 (payback < 8.5 years)

### Understanding Results

**Positive Net Marginal Profit**: Battery operations are economically beneficial
**Negative Net Marginal Profit**: Battery degradation costs exceed arbitrage revenue
**High Equivalent Cycles**: Aggressive trading, faster battery wear
**Payback > 10 years**: Poor ROI for battery investment

## Important Notes

### No Strategy Logic Changes
The tariff scenarios use the same underlying battery model and constraint logic as the original backtest. They only:
- Vary the import/export price tariffs
- Calculate economic metrics for each tariff scenario
- Provide structured reporting

### Economic Assumptions
- Degradation cost: $0.05/kWh moved (one way)
- Battery system cost: $15,000 (hardware) + $2,000 (installation)
- Simple payback: Single-factor ROI (doesn't account for time value of money)
- Annualisation: Linear extrapolation (assumes conditions persist)

### Dataset Sensitivity
Results are sensitive to:
- Price volatility (higher volatility → better arbitrage opportunities)
- Seasonal patterns (summer vs winter trading opportunities)
- Tariff structures (even small changes significantly impact economics)
- Battery efficiency and degradation assumptions

## Configuration

To customize scenario economics, edit [src/config.py](src/config.py):

```python
# Economics
DEGRADATION_COST_PER_KWH = 0.05  # Cost per kWh cycled

# Battery system costs
BATTERY_PURCHASE_COST = 15000  # Battery hardware
INSTALLATION_COST = 2000       # Installation
TOTAL_BATTERY_SYSTEM_COST = BATTERY_PURCHASE_COST + INSTALLATION_COST
```

To customize scenario tariffs, edit [src/tariff_scenarios.py](src/tariff_scenarios.py) or create new scenarios programmatically.

## Testing

Run the scenario tests:

```bash
python3 -m pytest tests/test_tariff_scenarios.py -v
```

Tests verify:
- Scenario definitions and economic assumptions
- Profit calculations (gross, degradation, net, annual)
- Payback calculations
- Consistency across runs
- Scenario comparison logic
