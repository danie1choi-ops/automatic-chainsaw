"""Solar generation and household load modelling."""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
import numpy as np
from src import config


@dataclass
class SolarProfile:
    """Daily solar generation profile (e.g., bell curve)."""
    peak_hour: float  # Hour of peak (e.g., 12.0 for noon)
    peak_power_kw: float  # Peak power in kW
    sunrise_hour: float  # Sunrise hour
    sunset_hour: float  # Sunset hour
    
    def get_power_kw(self, hour: float) -> float:
        """Get solar power for given hour.
        
        Args:
            hour: Hour of day (0-24).
            
        Returns:
            Power in kW.
        """
        # No generation outside sunrise/sunset
        if hour < self.sunrise_hour or hour > self.sunset_hour:
            return 0.0
        
        # Bell curve (normal distribution) centered at peak hour
        std_dev = (self.sunset_hour - self.sunrise_hour) / 4  # 4σ span
        exponent = -0.5 * ((hour - self.peak_hour) / std_dev) ** 2
        power = self.peak_power_kw * np.exp(exponent)
        
        return max(0.0, power)


@dataclass
class HouseholdLoad:
    """Daily household electricity demand profile."""
    # Load profile: dict of hour -> power in kW
    hourly_profile: dict  # e.g., {0: 0.5, 6: 1.2, 12: 0.8, 18: 2.0, 22: 1.0}
    
    def get_power_kw(self, hour: float) -> float:
        """Get household load for given hour.
        
        Args:
            hour: Hour of day (0-24).
            
        Returns:
            Load in kW.
        """
        # Interpolate between hourly values
        hour_floor = int(hour)
        hour_ceil = (hour_floor + 1) % 24
        fraction = hour - hour_floor
        
        power_floor = self.hourly_profile.get(hour_floor, 0.5)
        power_ceil = self.hourly_profile.get(hour_ceil, 0.5)
        
        return power_floor * (1 - fraction) + power_ceil * fraction


# Default solar profile: typical Australian rooftop solar
DEFAULT_SOLAR_PROFILE = SolarProfile(
    peak_hour=12.0,      # Noon
    peak_power_kw=8.0,   # 8kW peak (typical rooftop install)
    sunrise_hour=6.0,    # 6 AM
    sunset_hour=18.0,    # 6 PM
)

# Default household load profile: typical Australian home
DEFAULT_HOUSEHOLD_LOAD = HouseholdLoad(
    hourly_profile={
        0: 0.3,    # Midnight: 300W (baseline)
        1: 0.3,
        2: 0.3,
        3: 0.3,
        4: 0.3,
        5: 0.4,    # Early morning: 400W
        6: 0.8,    # 6 AM: morning activity
        7: 1.2,    # 7 AM: peak morning
        8: 0.9,    # 8 AM: some activity
        9: 0.6,    # 9 AM: less activity
        10: 0.5,   # 10 AM
        11: 0.6,   # 11 AM
        12: 0.9,   # Noon: lunch
        13: 0.7,   # 1 PM
        14: 0.5,   # 2 PM
        15: 0.5,   # 3 PM
        16: 0.6,   # 4 PM
        17: 1.5,   # 5 PM: dinner prep
        18: 2.0,   # 6 PM: peak evening
        19: 1.8,   # 7 PM: peak evening
        20: 1.5,   # 8 PM
        21: 1.2,   # 9 PM
        22: 0.8,   # 10 PM: winding down
        23: 0.5,   # 11 PM
    }
)


def get_solar_generation_kwh(
    timestamp: datetime,
    solar_profile: SolarProfile = None,
    interval_minutes: int = None,
) -> float:
    """Get solar energy generated in interval.
    
    Args:
        timestamp: Timestamp of interval start.
        solar_profile: Solar profile (default: DEFAULT_SOLAR_PROFILE).
        interval_minutes: Interval duration in minutes (default: config.INTERVAL_MINUTES).
        
    Returns:
        Energy generated in kWh.
    """
    if solar_profile is None:
        solar_profile = DEFAULT_SOLAR_PROFILE
    if interval_minutes is None:
        interval_minutes = config.INTERVAL_MINUTES
    
    # Get hour (with fractional part for interval)
    hour = timestamp.hour + timestamp.minute / 60.0
    
    # Get power at start of interval
    power_kw = solar_profile.get_power_kw(hour)
    
    # Convert to energy
    interval_hours = interval_minutes / 60.0
    energy_kwh = power_kw * interval_hours
    
    return max(0.0, energy_kwh)


def get_household_load_kwh(
    timestamp: datetime,
    household_load: HouseholdLoad = None,
    interval_minutes: int = None,
) -> float:
    """Get household demand in interval.
    
    Args:
        timestamp: Timestamp of interval start.
        household_load: Load profile (default: DEFAULT_HOUSEHOLD_LOAD).
        interval_minutes: Interval duration in minutes (default: config.INTERVAL_MINUTES).
        
    Returns:
        Energy consumed in kWh.
    """
    if household_load is None:
        household_load = DEFAULT_HOUSEHOLD_LOAD
    if interval_minutes is None:
        interval_minutes = config.INTERVAL_MINUTES
    
    # Get hour (with fractional part)
    hour = timestamp.hour + timestamp.minute / 60.0
    
    # Get power
    power_kw = household_load.get_power_kw(hour)
    
    # Convert to energy
    interval_hours = interval_minutes / 60.0
    energy_kwh = power_kw * interval_hours
    
    return max(0.0, energy_kwh)


@dataclass
class SolarLoadResults:
    """Results from solar generation and load modelling."""
    total_solar_generated_kwh: float
    total_household_demand_kwh: float
    total_grid_import_kwh: float
    total_solar_self_consumed_kwh: float
    total_solar_exported_kwh: float
    total_battery_charged_from_solar_kwh: float
    total_battery_discharged_to_load_kwh: float
    total_battery_discharged_to_export_kwh: float
    
    # Economic metrics
    grid_import_cost_without_solar: float
    grid_import_cost_with_solar: float
    solar_savings: float  # Cost avoided from solar
    
    # With arbitrage on top
    arbitrage_profit_on_top: float
    total_benefit: float  # Solar savings + arbitrage profit
    
    def __str__(self) -> str:
        """Pretty print results."""
        return f"""
SOLAR + LOAD + ARBITRAGE ANALYSIS
{'=' * 70}

Solar Generation:
  Total Generated:              {self.total_solar_generated_kwh:>10.2f} kWh
  Self-Consumed:                {self.total_solar_self_consumed_kwh:>10.2f} kWh ({100*self.total_solar_self_consumed_kwh/max(self.total_solar_generated_kwh, 0.01):>5.1f}%)
  Exported to Grid:             {self.total_solar_exported_kwh:>10.2f} kWh ({100*self.total_solar_exported_kwh/max(self.total_solar_generated_kwh, 0.01):>5.1f}%)

Household Demand:
  Total Demand:                 {self.total_household_demand_kwh:>10.2f} kWh
  From Grid (no solar):         {self.grid_import_cost_without_solar/0.30:>10.2f} kWh
  From Grid (with solar):       {self.total_grid_import_kwh:>10.2f} kWh

Battery Usage:
  Charged from Solar:           {self.total_battery_charged_from_solar_kwh:>10.2f} kWh
  Discharged to Load:           {self.total_battery_discharged_to_load_kwh:>10.2f} kWh
  Discharged to Export:         {self.total_battery_discharged_to_export_kwh:>10.2f} kWh

Economic Analysis:
  Grid Import Cost (no solar):  ${self.grid_import_cost_without_solar:>10.2f}
  Grid Import Cost (with solar):${self.grid_import_cost_with_solar:>10.2f}
  {'-' * 70}
  Solar Savings:                ${self.solar_savings:>10.2f}
  
  Arbitrage Profit:             ${self.arbitrage_profit_on_top:>10.2f}
  {'-' * 70}
  Total Benefit:                ${self.total_benefit:>10.2f}

{'=' * 70}
"""
