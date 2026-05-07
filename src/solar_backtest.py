"""Backtest engine with solar generation and household load."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src import config
from src.data_loader import PricePoint, load_price_data
from src.battery_model import BatteryModel
from src.strategy import Action, get_action
from src.solar_load_model import (
    SolarProfile,
    HouseholdLoad,
    DEFAULT_SOLAR_PROFILE,
    DEFAULT_HOUSEHOLD_LOAD,
    get_solar_generation_kwh,
    get_household_load_kwh,
    SolarLoadResults,
)


OUTPUT_DIR = Path("outputs")
SOLAR_BACKTEST_OUTPUT = OUTPUT_DIR / "solar_backtest_results.csv"


def run_solar_backtest(
    price_data: List[PricePoint],
    solar_profile: SolarProfile = None,
    household_load: HouseholdLoad = None,
    import_price_per_kwh: float = 0.30,  # Average grid import price
) -> tuple:
    """Run backtest with solar generation and household load.
    
    Args:
        price_data: List of PricePoint objects.
        solar_profile: Solar generation profile (default: DEFAULT_SOLAR_PROFILE).
        household_load: Household load profile (default: DEFAULT_HOUSEHOLD_LOAD).
        import_price_per_kwh: Average grid import price for cost calculation.
        
    Returns:
        Tuple of (backtest_results_dict, SolarLoadResults).
    """
    if solar_profile is None:
        solar_profile = DEFAULT_SOLAR_PROFILE
    if household_load is None:
        household_load = DEFAULT_HOUSEHOLD_LOAD
    
    # Initialize battery
    battery = BatteryModel()
    
    # Tracking variables
    total_solar_generated = 0.0
    total_household_demand = 0.0
    total_grid_import = 0.0
    total_solar_self_consumed = 0.0
    total_solar_exported = 0.0
    total_battery_charged_from_solar = 0.0
    total_battery_discharged_to_load = 0.0
    total_battery_discharged_to_export = 0.0
    
    # Arbitrage tracking
    total_arbitrage_cashflow = 0.0
    total_degradation_cost = 0.0
    export_count = 0
    
    price_history = []
    interval_results = []
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Clear previous output
    if SOLAR_BACKTEST_OUTPUT.exists():
        SOLAR_BACKTEST_OUTPUT.unlink()
    
    # Write CSV header
    with open(SOLAR_BACKTEST_OUTPUT, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'solar_kwh', 'demand_kwh', 'grid_import_kwh',
            'arbitrage_action', 'battery_charged_kwh', 'battery_discharged_kwh',
            'soc_percent', 'battery_energy_kwh'
        ])
    
    # Process each price point
    for i, price_point in enumerate(price_data):
        interval_hours = config.INTERVAL_MINUTES / 60.0
        
        # Get solar generation for this interval
        solar_kwh = get_solar_generation_kwh(price_point.timestamp, solar_profile)
        total_solar_generated += solar_kwh
        
        # Get household demand for this interval
        demand_kwh = get_household_load_kwh(price_point.timestamp, household_load)
        total_household_demand += demand_kwh
        
        # ===== ENERGY FLOW LOGIC =====
        # 1. Solar feeds into battery first
        solar_available = solar_kwh
        battery_charge_from_solar = battery.charge(solar_available, interval_hours)
        solar_available -= battery_charge_from_solar
        total_battery_charged_from_solar += battery_charge_from_solar
        
        # 2. Remaining solar exported to grid
        solar_to_export = solar_available
        total_solar_exported += solar_to_export
        
        # 3. Household demand consumed from battery first
        demand_remaining = demand_kwh
        battery_discharge_to_load = battery.discharge(demand_remaining, interval_hours)
        demand_remaining -= battery_discharge_to_load
        total_battery_discharged_to_load += battery_discharge_to_load
        
        # 4. Remaining demand from grid
        grid_import_for_load = demand_remaining
        total_grid_import += grid_import_for_load
        
        # Track solar self-consumption: solar that's used locally (not exported)
        # This includes solar stored in battery and then discharged for load
        solar_self_consumed_this_interval = solar_kwh - solar_to_export
        total_solar_self_consumed += solar_self_consumed_this_interval
        
        # ===== ARBITRAGE LOGIC =====
        # Add current price to history
        price_history.append(price_point.price_per_kwh)
        
        # Get arbitrage action
        action = get_action(
            price=price_point.price_per_kwh,
            soc_percent=battery.soc_percent,
            price_history=price_history,
            timestamp=price_point.timestamp,
        )
        
        arbitrage_cashflow = 0.0
        battery_charged_arbitrage = 0.0
        battery_discharged_arbitrage = 0.0
        
        # Execute arbitrage action
        if action == Action.CHARGE:
            usable_capacity = config.BATTERY_CAPACITY_KWH * 0.75
            max_power_kwh = config.MAX_CHARGE_KW * interval_hours
            energy_amount = min(usable_capacity, max_power_kwh)
            
            actual_charge = battery.charge(energy_amount, interval_hours)
            battery_charged_arbitrage = actual_charge
            # Cost to charge (negative cashflow)
            arbitrage_cashflow = -actual_charge * price_point.price_per_kwh
            
        elif action == Action.EXPORT:
            export_count += 1
            
            # Calculate dynamic export fraction
            window_size = 288
            export_percentile = 0.95
            dynamic_threshold = config.EXPORT_PRICE_THRESHOLD
            if len(price_history) >= window_size:
                import numpy as np
                recent_prices = price_history[-window_size:]
                dynamic_threshold = np.percentile(recent_prices, export_percentile * 100)
            
            strength = price_point.price_per_kwh / dynamic_threshold
            
            if strength >= 1.5:
                export_fraction = 1.0
            elif strength >= 1.2:
                export_fraction = 0.5
            else:
                export_fraction = 0.2
            
            soc_ratio = battery.soc_percent / config.MAX_SOC_PERCENT
            if soc_ratio > 0.8:
                export_fraction += 0.2
            elif soc_ratio < 0.4:
                export_fraction -= 0.1
            
            export_fraction = max(0.1, min(1.0, export_fraction))
            
            usable_capacity = config.BATTERY_CAPACITY_KWH * 0.75
            max_power_kwh = config.MAX_DISCHARGE_KW * interval_hours
            available_energy = min(usable_capacity, max_power_kwh)
            energy_amount = export_fraction * available_energy
            
            actual_discharge = battery.discharge(energy_amount, interval_hours)
            battery_discharged_arbitrage = actual_discharge
            # Revenue from export
            arbitrage_cashflow = actual_discharge * price_point.price_per_kwh
            total_battery_discharged_to_export += actual_discharge
        
        # Calculate degradation cost (for all energy moved)
        total_energy_moved = battery_charged_arbitrage + battery_discharged_arbitrage
        degradation_cost = total_energy_moved * config.DEGRADATION_COST_PER_KWH
        total_degradation_cost += degradation_cost
        
        # Net arbitrage cashflow
        net_arbitrage_cashflow = arbitrage_cashflow - degradation_cost
        total_arbitrage_cashflow += net_arbitrage_cashflow
        
        # Log result
        interval_results.append({
            'timestamp': price_point.timestamp,
            'solar_kwh': solar_kwh,
            'demand_kwh': demand_kwh,
            'grid_import_kwh': grid_import_for_load,
            'action': action,
            'soc_percent': battery.soc_percent,
        })
        
        # Write to CSV
        with open(SOLAR_BACKTEST_OUTPUT, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                price_point.timestamp.isoformat(),
                f"{solar_kwh:.3f}",
                f"{demand_kwh:.3f}",
                f"{grid_import_for_load:.3f}",
                action,
                f"{battery_charged_arbitrage:.3f}",
                f"{battery_discharged_arbitrage:.3f}",
                f"{battery.soc_percent:.1f}",
                f"{battery.energy_stored_kwh:.3f}",
            ])
    
    # Calculate costs
    grid_import_cost_without_solar = total_household_demand * import_price_per_kwh
    grid_import_cost_with_solar = total_grid_import * import_price_per_kwh
    solar_savings = grid_import_cost_without_solar - grid_import_cost_with_solar
    
    # Total arbitrage profit (cashflow - degradation)
    arbitrage_profit = total_arbitrage_cashflow
    
    # Total benefit
    total_benefit = solar_savings + arbitrage_profit
    
    # Create results
    solar_load_results = SolarLoadResults(
        total_solar_generated_kwh=total_solar_generated,
        total_household_demand_kwh=total_household_demand,
        total_grid_import_kwh=total_grid_import,
        total_solar_self_consumed_kwh=total_solar_self_consumed,
        total_solar_exported_kwh=total_solar_exported,
        total_battery_charged_from_solar_kwh=total_battery_charged_from_solar,
        total_battery_discharged_to_load_kwh=total_battery_discharged_to_load,
        total_battery_discharged_to_export_kwh=total_battery_discharged_to_export,
        grid_import_cost_without_solar=grid_import_cost_without_solar,
        grid_import_cost_with_solar=grid_import_cost_with_solar,
        solar_savings=solar_savings,
        arbitrage_profit_on_top=arbitrage_profit,
        total_benefit=total_benefit,
    )
    
    backtest_results = {
        'total_solar_generated': total_solar_generated,
        'total_household_demand': total_household_demand,
        'total_grid_import': total_grid_import,
        'total_solar_self_consumed': total_solar_self_consumed,
        'total_solar_exported': total_solar_exported,
        'grid_import_cost_without_solar': grid_import_cost_without_solar,
        'grid_import_cost_with_solar': grid_import_cost_with_solar,
        'solar_savings': solar_savings,
        'arbitrage_profit': arbitrage_profit,
        'total_benefit': total_benefit,
        'num_intervals': len(price_data),
        'ending_soc': battery.soc_percent,
    }
    
    return backtest_results, solar_load_results


def print_solar_backtest_results(results: dict):
    """Print solar backtest results."""
    print("\n" + "=" * 70)
    print("SOLAR BACKTEST RESULTS")
    print("=" * 70)
    print(f"Total Intervals:              {results['num_intervals']}")
    print(f"Total Solar Generated:        {results['total_solar_generated']:.2f} kWh")
    print(f"Total Household Demand:       {results['total_household_demand']:.2f} kWh")
    print(f"Total Grid Import:            {results['total_grid_import']:.2f} kWh")
    print(f"Total Solar Self-Consumed:    {results['total_solar_self_consumed']:.2f} kWh")
    print(f"Total Solar Exported:         {results['total_solar_exported']:.2f} kWh")
    print("-" * 70)
    print(f"Grid Cost (no solar):         ${results['grid_import_cost_without_solar']:.2f}")
    print(f"Grid Cost (with solar):       ${results['grid_import_cost_with_solar']:.2f}")
    print(f"Solar Savings:                ${results['solar_savings']:.2f}")
    print(f"Arbitrage Profit:             ${results['arbitrage_profit']:.2f}")
    print(f"Total Benefit:                ${results['total_benefit']:.2f}")
    print(f"Ending SoC:                   {results['ending_soc']:.1f}%")
    print("=" * 70)
