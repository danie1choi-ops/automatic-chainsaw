"""Backtest engine for running historical simulations."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from src import config
from src.data_loader import PricePoint, load_price_data
from src.battery_model import BatteryModel
from src.strategy import Strategy, Action


# Output directory
OUTPUT_DIR = Path("outputs")
BACKTEST_OUTPUT = OUTPUT_DIR / "backtest_results.csv"


def run_backtest(price_data: List[PricePoint]) -> dict:
    """Run a backtest on historical price data.
    
    Args:
        price_data: List of PricePoint objects.
        
    Returns:
        Dictionary with backtest results.
    """
    # Initialize components
    battery = BatteryModel()
    strategy = Strategy()
    
    # Tracking variables
    total_gross_profit = 0.0
    total_degradation_cost = 0.0
    total_charged_kwh = 0.0
    total_exported_kwh = 0.0
    interval_results = []
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Clear previous output file
    if BACKTEST_OUTPUT.exists():
        BACKTEST_OUTPUT.unlink()
    
    # Write CSV header
    with open(BACKTEST_OUTPUT, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'price_per_kwh', 'action', 'reason',
            'soc_percent', 'energy_kwh', 'cashflow', 'cumulative_profit'
        ])
    
    cumulative_profit = 0.0
    
    # Process each price point
    for i, price_point in enumerate(price_data):
        # Get previous SoC
        prev_soc = battery.soc_percent
        
        # Make decision
        decision = strategy.decide(
            price_per_kwh=price_point.price_per_kwh,
            battery_soc_percent=battery.soc_percent,
        )
        
        # Calculate energy amount
        interval_hours = config.INTERVAL_MINUTES / 60.0
        energy_amount = strategy.calculate_energy_amount(
            decision=decision,
            battery_capacity_kwh=config.BATTERY_CAPACITY_KWH,
            interval_hours=interval_hours,
        )
        
        # Execute action
        energy_kwh = 0.0
        cashflow = 0.0
        
        if decision.action == Action.CHARGE:
            # Calculate how much we can actually charge
            actual_charge = battery.charge(energy_amount, interval_hours)
            energy_kwh = actual_charge
            # Cost to charge (negative cashflow)
            cashflow = -actual_charge * price_point.price_per_kwh
            total_charged_kwh += actual_charge
            
        elif decision.action == Action.EXPORT:
            # Calculate how much we can actually discharge
            actual_discharge = battery.discharge(energy_amount, interval_hours)
            energy_kwh = -actual_discharge
            # Revenue from export (positive cashflow)
            cashflow = actual_discharge * price_point.price_per_kwh
            total_exported_kwh += actual_discharge
        
        # Calculate degradation cost
        degradation_cost = abs(energy_kwh) * config.DEGRADATION_COST_PER_KWH
        total_degradation_cost += degradation_cost
        
        # Net cashflow
        net_cashflow = cashflow - degradation_cost
        cumulative_profit += net_cashflow
        total_gross_profit += cashflow
        
        # Log result
        interval_results.append({
            'timestamp': price_point.timestamp,
            'price_per_kwh': price_point.price_per_kwh,
            'action': decision.action,
            'reason': decision.reason,
            'soc_percent': battery.soc_percent,
            'energy_kwh': energy_kwh,
            'cashflow': net_cashflow,
            'cumulative_profit': cumulative_profit,
        })
        
        # Write to CSV
        with open(BACKTEST_OUTPUT, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                price_point.timestamp.isoformat(),
                price_point.price_per_kwh,
                decision.action,
                decision.reason,
                f"{battery.soc_percent:.1f}",
                f"{energy_kwh:.3f}",
                f"{net_cashflow:.4f}",
                f"{cumulative_profit:.4f}",
            ])
    
    # Calculate equivalent full cycles
    total_energy_moved = total_charged_kwh + total_exported_kwh
    equivalent_cycles = total_energy_moved / config.BATTERY_CAPACITY_KWH if config.BATTERY_CAPACITY_KWH > 0 else 0
    
    return {
        'total_gross_profit': total_gross_profit,
        'total_degradation_cost': total_degradation_cost,
        'net_profit': total_gross_profit - total_degradation_cost,
        'total_charged_kwh': total_charged_kwh,
        'total_exported_kwh': total_exported_kwh,
        'equivalent_cycles': equivalent_cycles,
        'ending_soc': battery.soc_percent,
        'num_intervals': len(price_data),
    }


def print_backtest_results(results: dict):
    """Print backtest results in a readable format."""
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Intervals:     {results['num_intervals']}")
    print(f"Total Gross Profit:  ${results['total_gross_profit']:.2f}")
    print(f"Degradation Cost:    ${results['total_degradation_cost']:.2f}")
    print(f"Net Profit:          ${results['net_profit']:.2f}")
    print("-" * 60)
    print(f"Charged kWh:         {results['total_charged_kwh']:.2f} kWh")
    print(f"Exported kWh:        {results['total_exported_kwh']:.2f} kWh")
    print(f"Equivalent Cycles:   {results['equivalent_cycles']:.2f}")
    print(f"Ending SoC:          {results['ending_soc']:.1f}%")
    print("=" * 60)