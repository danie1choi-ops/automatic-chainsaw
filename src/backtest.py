"""Backtest engine for running historical simulations."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List
import numpy as np

from src import config
from src.data_loader import PricePoint, load_price_data
from src.battery_model import BatteryModel
from src.strategy import Action, get_action


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
    
    # Tracking variables
    total_gross_profit = 0.0
    total_degradation_cost = 0.0
    total_charged_kwh = 0.0
    total_exported_kwh = 0.0
    export_count = 0
    price_history = []  # Rolling price history for dynamic threshold
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
        # Add current price to history for dynamic threshold calculation
        price_history.append(price_point.price_per_kwh)
        
        # Get action using strategy function with dynamic threshold
        action = get_action(
            price=price_point.price_per_kwh,
            soc_percent=battery.soc_percent,
            price_history=price_history,
            timestamp=price_point.timestamp,
        )
        
        # Determine reason
        if action == Action.CHARGE:
            reason = f"Price {price_point.price_per_kwh:.4f} <= threshold {config.CHARGE_PRICE_THRESHOLD:.4f}"
        elif action == Action.EXPORT:
            reason = f"Price {price_point.price_per_kwh:.4f} >= threshold {config.EXPORT_PRICE_THRESHOLD:.4f}"
        else:
            reason = "No price signal or SoC constraint"
        
        # Calculate energy amount
        interval_hours = config.INTERVAL_MINUTES / 60.0
        energy_kwh = 0.0
        cashflow = 0.0
        
        # Execute action
        if action == Action.CHARGE:
            # Full usable capacity per interval
            usable_capacity = config.BATTERY_CAPACITY_KWH * 0.75
            max_power_kwh = config.MAX_CHARGE_KW * interval_hours
            energy_amount = min(usable_capacity, max_power_kwh)
            
            # Calculate how much we can actually charge
            actual_charge = battery.charge(energy_amount, interval_hours)
            energy_kwh = actual_charge
            # Cost to charge (negative cashflow)
            cashflow = -actual_charge * price_point.price_per_kwh
            total_charged_kwh += actual_charge
            
            # Assert SoC stays within bounds
            assert battery.soc_percent >= config.MIN_SOC_PERCENT, \
                f"CHARGE action: SoC {battery.soc_percent:.1f}% dropped below MIN {config.MIN_SOC_PERCENT}%"
            assert battery.soc_percent <= config.MAX_SOC_PERCENT, \
                f"CHARGE action: SoC {battery.soc_percent:.1f}% exceeded MAX {config.MAX_SOC_PERCENT}%"
            
        elif action == Action.EXPORT:
            export_count += 1
            
            # Calculate dynamic threshold for export fraction
            window_size = 288
            export_percentile = 0.95
            static_export_threshold = config.EXPORT_PRICE_THRESHOLD
            dynamic_threshold = static_export_threshold
            if len(price_history) >= window_size:
                recent_prices = price_history[-window_size:]
                dynamic_threshold = np.percentile(recent_prices, export_percentile * 100)
            
            # Compute price strength
            strength = price_point.price_per_kwh / dynamic_threshold
            
            # Define export fraction based on price strength
            if strength >= 1.5:
                export_fraction = 1.0
            elif strength >= 1.2:
                export_fraction = 0.5
            else:
                export_fraction = 0.2
            
            # Adjust export fraction based on battery SoC
            soc_ratio = battery.soc_percent / config.MAX_SOC_PERCENT
            if soc_ratio > 0.8:
                export_fraction += 0.2
            elif soc_ratio < 0.4:
                export_fraction -= 0.1
            
            # Clamp between 0.1 and 1.0
            export_fraction = max(0.1, min(1.0, export_fraction))
            
            # Available energy per interval
            usable_capacity = config.BATTERY_CAPACITY_KWH * 0.75
            max_power_kwh = config.MAX_DISCHARGE_KW * interval_hours
            available_energy = min(usable_capacity, max_power_kwh)
            energy_amount = export_fraction * available_energy
            
            # Calculate how much we can actually discharge
            actual_discharge = battery.discharge(energy_amount, interval_hours)
            energy_kwh = -actual_discharge
            # Revenue from export (positive cashflow)
            cashflow = actual_discharge * price_point.price_per_kwh
            total_exported_kwh += actual_discharge
            
            # Assert SoC stays within bounds
            assert battery.soc_percent >= config.MIN_SOC_PERCENT, \
                f"EXPORT action: SoC {battery.soc_percent:.1f}% dropped below MIN {config.MIN_SOC_PERCENT}%"
            assert battery.soc_percent <= config.MAX_SOC_PERCENT, \
                f"EXPORT action: SoC {battery.soc_percent:.1f}% exceeded MAX {config.MAX_SOC_PERCENT}%"
        
        # Calculate degradation cost
        degradation_cost = abs(energy_kwh) * config.DEGRADATION_COST_PER_KWH
        total_degradation_cost += degradation_cost
        
        # Net cashflow
        net_cashflow = cashflow - degradation_cost
        cumulative_profit += net_cashflow
        total_gross_profit += cashflow
        
        # Final assertion: SoC must remain within valid bounds
        assert battery.soc_percent >= config.MIN_SOC_PERCENT, \
            f"Interval {i}: SoC {battery.soc_percent:.1f}% dropped below MIN {config.MIN_SOC_PERCENT}%"
        assert battery.soc_percent <= config.MAX_SOC_PERCENT, \
            f"Interval {i}: SoC {battery.soc_percent:.1f}% exceeded MAX {config.MAX_SOC_PERCENT}%"
        
        # Log result
        interval_results.append({
            'timestamp': price_point.timestamp,
            'price_per_kwh': price_point.price_per_kwh,
            'action': action,
            'reason': reason,
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
                action,
                reason,
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
        'export_count': export_count,
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
    print(f"Total EXPORT actions: {results['export_count']}")
    print(f"Equivalent Cycles:   {results['equivalent_cycles']:.2f}")
    print(f"Ending SoC:          {results['ending_soc']:.1f}%")
    print("=" * 60)