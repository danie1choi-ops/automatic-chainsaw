"""Tariff scenario modelling for energy arbitrage economics."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np
from src import config
from src.data_loader import PricePoint
from src.battery_model import BatteryModel
from src.strategy import get_action, Action


@dataclass
class TariffScenario:
    """Defines a tariff scenario with import/export pricing."""
    name: str
    description: str
    import_price_per_kwh: float  # Price to import from grid
    export_price_per_kwh: float  # Price to export to grid
    # Override config thresholds for this scenario
    charge_threshold: Optional[float] = None
    export_threshold: Optional[float] = None
    # Override battery system cost for payback (e.g., 0 for existing battery)
    system_cost_override: Optional[float] = None


@dataclass
class ScenarioResults:
    """Results from running a tariff scenario."""
    scenario: TariffScenario
    gross_profit: float  # Total revenue from arbitrage
    degradation_cost: float  # Total battery degradation cost
    net_marginal_profit: float  # Gross profit - degradation
    total_charged_kwh: float
    total_exported_kwh: float
    equivalent_cycles: float
    period_days: float
    annualised_profit: float  # Profit per year
    simple_payback_years: Optional[float]  # Years to payback investment
    ending_soc: float
    export_count: int
    
    def __str__(self) -> str:
        """Pretty print scenario results."""
        payback_str = f"{self.simple_payback_years:.1f} years" if self.simple_payback_years else "Never"
        return f"""
{self.scenario.name}
{'-' * 70}
  {self.scenario.description}
  
  Import Price:      ${self.scenario.import_price_per_kwh:.4f}/kWh
  Export Price:      ${self.scenario.export_price_per_kwh:.4f}/kWh
  
  Period Performance:
    Gross Profit:       ${self.gross_profit:>10.2f}
    Degradation Cost:   ${self.degradation_cost:>10.2f}
    Net Marginal Profit:${self.net_marginal_profit:>10.2f}
    
  Operating Metrics:
    Charged Energy:     {self.total_charged_kwh:>10.2f} kWh
    Exported Energy:    {self.total_exported_kwh:>10.2f} kWh
    Equivalent Cycles:  {self.equivalent_cycles:>10.2f} cycles
    Export Actions:     {self.export_count:>10} times
    
  Period Analysis:
    Period Duration:    {self.period_days:>10.1f} days
    Annualised Profit:  ${self.annualised_profit:>10.2f}/year
    
  Investment Analysis:
    Simple Payback:     {payback_str:>10}
    Ending SoC:         {self.ending_soc:>10.1f}%
"""


# Define four standard tariff scenarios
TARIFF_SCENARIOS: List[TariffScenario] = [
    TariffScenario(
        name="Wholesale Arbitrage Mode",
        description=(
            "Pure wholesale market arbitrage. Battery cycles based solely on "
            "price spreads. Typical for commercial operations with AEMO market access."
        ),
        import_price_per_kwh=0.10,  # Typical wholesale buy
        export_price_per_kwh=0.15,  # Typical wholesale sell
        charge_threshold=0.10,
        export_threshold=0.15,
        system_cost_override=config.TOTAL_BATTERY_SYSTEM_COST,  # Full system cost
    ),
    TariffScenario(
        name="Retail Import/Feed-in Tariff Mode",
        description=(
            "Household retail scenario. Import from retailer at higher rate, "
            "export to grid at lower feed-in tariff. Limited arbitrage margin."
        ),
        import_price_per_kwh=0.35,  # Typical retail import (high)
        export_price_per_kwh=0.12,  # Typical feed-in tariff (low)
        charge_threshold=0.35,
        export_threshold=0.12,
        system_cost_override=config.TOTAL_BATTERY_SYSTEM_COST,  # Full system cost
    ),
    TariffScenario(
        name="Existing Battery Marginal Mode",
        description=(
            "System already owns battery (e.g., existing install). "
            "Only marginal costs count (degradation). No capital payback required."
        ),
        import_price_per_kwh=0.25,  # Mid-range retail
        export_price_per_kwh=0.15,  # Mid-range export (better than feed-in)
        charge_threshold=0.25,
        export_threshold=0.15,
        system_cost_override=0.0,  # No capital cost - already owned
    ),
    TariffScenario(
        name="New Battery Full-Cost Mode",
        description=(
            "New battery purchase with installation. Full capital cost recovery "
            "needed with typical 10-year horizon. Includes all system costs."
        ),
        import_price_per_kwh=0.30,  # Moderate retail
        export_price_per_kwh=0.18,  # Good export opportunity
        charge_threshold=0.30,
        export_threshold=0.18,
        system_cost_override=config.TOTAL_BATTERY_SYSTEM_COST,  # Full system cost
    ),
]


def run_scenario(
    scenario: TariffScenario,
    price_data: List[PricePoint],
) -> ScenarioResults:
    """Run a tariff scenario on price data.
    
    Args:
        scenario: TariffScenario to run.
        price_data: List of PricePoint objects.
        
    Returns:
        ScenarioResults with performance metrics.
    """
    # Initialize battery model
    battery = BatteryModel()
    
    # Override price thresholds if specified
    charge_threshold = scenario.charge_threshold or config.CHARGE_PRICE_THRESHOLD
    export_threshold = scenario.export_threshold or config.EXPORT_PRICE_THRESHOLD
    
    # Tracking variables
    total_gross_profit = 0.0
    total_degradation_cost = 0.0
    total_charged_kwh = 0.0
    total_exported_kwh = 0.0
    export_count = 0
    price_history = []
    
    # Process each price point
    for price_point in price_data:
        price_history.append(price_point.price_per_kwh)
        
        # Determine action based on scenario tariffs
        # Use scenario's import price for "charging is like buying at this price"
        action = Action.HOLD
        energy_kwh = 0.0
        cashflow = 0.0
        
        interval_hours = config.INTERVAL_MINUTES / 60.0
        
        # Simple rule: charge if price <= import tariff, export if >= export tariff
        if (price_point.price_per_kwh <= scenario.import_price_per_kwh and 
            battery.soc_percent < config.MAX_SOC_PERCENT):
            action = Action.CHARGE
            usable_capacity = config.BATTERY_CAPACITY_KWH * 0.75
            max_power_kwh = config.MAX_CHARGE_KW * interval_hours
            energy_amount = min(usable_capacity, max_power_kwh)
            actual_charge = battery.charge(energy_amount, interval_hours)
            energy_kwh = actual_charge
            # Cost of importing at scenario tariff
            cashflow = -actual_charge * scenario.import_price_per_kwh
            total_charged_kwh += actual_charge
            
        elif (price_point.price_per_kwh >= scenario.export_price_per_kwh and 
              battery.soc_percent > config.MIN_SOC_PERCENT):
            action = Action.EXPORT
            export_count += 1
            
            # Adaptive export fraction based on price strength
            spread = scenario.export_price_per_kwh - scenario.import_price_per_kwh
            if spread > 0:
                price_strength = (price_point.price_per_kwh - scenario.import_price_per_kwh) / spread
            else:
                price_strength = 1.0
            
            # Export more when price is very strong
            if price_strength >= 2.0:
                export_fraction = 1.0
            elif price_strength >= 1.5:
                export_fraction = 0.7
            elif price_strength >= 1.0:
                export_fraction = 0.4
            else:
                export_fraction = 0.1
            
            usable_capacity = config.BATTERY_CAPACITY_KWH * 0.75
            max_power_kwh = config.MAX_DISCHARGE_KW * interval_hours
            available_energy = min(usable_capacity, max_power_kwh)
            energy_amount = export_fraction * available_energy
            
            actual_discharge = battery.discharge(energy_amount, interval_hours)
            energy_kwh = -actual_discharge
            # Revenue from exporting at scenario tariff
            cashflow = actual_discharge * scenario.export_price_per_kwh
            total_exported_kwh += actual_discharge
        
        # Calculate degradation cost (applies to all energy moved)
        degradation_cost = abs(energy_kwh) * config.DEGRADATION_COST_PER_KWH
        total_degradation_cost += degradation_cost
        
        # Track gross profit (actual arbitrage profit)
        total_gross_profit += cashflow
    
    # Calculate equivalent full cycles
    total_energy_moved = total_charged_kwh + total_exported_kwh
    equivalent_cycles = (
        total_energy_moved / config.BATTERY_CAPACITY_KWH 
        if config.BATTERY_CAPACITY_KWH > 0 else 0
    )
    
    # Calculate period duration
    if len(price_data) > 1:
        first_timestamp = price_data[0].timestamp
        last_timestamp = price_data[-1].timestamp
        period_seconds = (last_timestamp - first_timestamp).total_seconds()
        period_days = period_seconds / (24 * 3600)
        if period_days < 1:
            period_days = 1
    else:
        period_days = 1
    
    # Calculate annualised profit (net of degradation)
    net_marginal_profit = total_gross_profit - total_degradation_cost
    annual_profit = net_marginal_profit * (365 / period_days)
    
    # Calculate simple payback
    system_cost = scenario.system_cost_override
    if system_cost is None:
        system_cost = config.TOTAL_BATTERY_SYSTEM_COST
    
    if system_cost > 0 and annual_profit > 0:
        simple_payback_years = system_cost / annual_profit
    else:
        simple_payback_years = None
    
    return ScenarioResults(
        scenario=scenario,
        gross_profit=total_gross_profit,
        degradation_cost=total_degradation_cost,
        net_marginal_profit=net_marginal_profit,
        total_charged_kwh=total_charged_kwh,
        total_exported_kwh=total_exported_kwh,
        equivalent_cycles=equivalent_cycles,
        period_days=period_days,
        annualised_profit=annual_profit,
        simple_payback_years=simple_payback_years,
        ending_soc=battery.soc_percent,
        export_count=export_count,
    )


def run_all_scenarios(price_data: List[PricePoint]) -> Dict[str, ScenarioResults]:
    """Run all four standard tariff scenarios.
    
    Args:
        price_data: List of PricePoint objects.
        
    Returns:
        Dictionary mapping scenario names to results.
    """
    results = {}
    for scenario in TARIFF_SCENARIOS:
        results[scenario.name] = run_scenario(scenario, price_data)
    return results


def print_scenario_summary(results: Dict[str, ScenarioResults]):
    """Print summary comparison of all scenarios.
    
    Args:
        results: Dictionary of scenario results.
    """
    print("\n" + "=" * 70)
    print("TARIFF SCENARIO ANALYSIS")
    print("=" * 70)
    
    # Print each scenario
    for name, result in results.items():
        print(result)
    
    # Print comparison table
    print("\n" + "=" * 70)
    print("SCENARIO COMPARISON")
    print("=" * 70)
    print(f"{'Scenario':<35} {'Period $':<12} {'Annual $':<12} {'Payback Yr':<12}")
    print("-" * 70)
    
    for name, result in results.items():
        payback_str = (
            f"{result.simple_payback_years:.1f}" 
            if result.simple_payback_years else "∞"
        )
        print(
            f"{name:<35} "
            f"${result.net_marginal_profit:>10.2f}  "
            f"${result.annualised_profit:>10.2f}  "
            f"{payback_str:>10}"
        )
    
    print("=" * 70)


def export_scenario_results_csv(results: Dict[str, ScenarioResults], filepath: str):
    """Export scenario results to CSV file.
    
    Args:
        results: Dictionary of scenario results.
        filepath: Path to write CSV file.
    """
    import csv
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow([
            'Scenario',
            'Import Price ($/kWh)',
            'Export Price ($/kWh)',
            'Gross Profit ($)',
            'Degradation Cost ($)',
            'Net Marginal Profit ($)',
            'Period Days',
            'Annualised Profit ($/year)',
            'Simple Payback (years)',
            'Charged Energy (kWh)',
            'Exported Energy (kWh)',
            'Equivalent Cycles',
            'Export Actions',
        ])
        
        # Data rows
        for name, result in results.items():
            payback = result.simple_payback_years if result.simple_payback_years else ''
            writer.writerow([
                name,
                f"{result.scenario.import_price_per_kwh:.4f}",
                f"{result.scenario.export_price_per_kwh:.4f}",
                f"{result.gross_profit:.2f}",
                f"{result.degradation_cost:.2f}",
                f"{result.net_marginal_profit:.2f}",
                f"{result.period_days:.1f}",
                f"{result.annualised_profit:.2f}",
                payback,
                f"{result.total_charged_kwh:.2f}",
                f"{result.total_exported_kwh:.2f}",
                f"{result.equivalent_cycles:.2f}",
                result.export_count,
            ])
