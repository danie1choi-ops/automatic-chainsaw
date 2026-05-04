"""Arbitrage strategy for battery charging/discharging decisions."""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import numpy as np
from src import config


class Action:
    """Possible actions for the arbitrage strategy."""
    CHARGE = "CHARGE"
    HOLD = "HOLD"
    EXPORT = "EXPORT"


@dataclass
class Decision:
    """A decision from the strategy."""
    action: str
    reason: str
    energy_kwh: float = 0.0  # Amount of energy to charge/discharge


class Strategy:
    """Rule-based arbitrage strategy."""
    
    def __init__(
        self,
        charge_price_threshold: float = None,
        export_price_threshold: float = None,
    ):
        """Initialize the strategy.
        
        Args:
            charge_price_threshold: Price below which to charge.
            export_price_threshold: Price above which to export.
        """
        self.charge_price_threshold = charge_price_threshold or config.CHARGE_PRICE_THRESHOLD
        self.export_price_threshold = export_price_threshold or config.EXPORT_PRICE_THRESHOLD
    
    def decide(
        self,
        price_per_kwh: float,
        battery_soc_percent: float,
        battery_max_soc: float = None,
        battery_min_soc: float = None,
        timestamp: datetime = None,
    ) -> Decision:
        """Make a decision based on current price and battery state.
        
        Args:
            price_per_kwh: Current electricity price in $/kWh.
            battery_soc_percent: Current battery state of charge in %.
            battery_max_soc: Maximum SoC limit (default from config).
            battery_min_soc: Minimum SoC limit (default from config).
            timestamp: Timestamp for time-of-day bias (optional).
            
        Returns:
            Decision object with action and reason.
        """
        max_soc = battery_max_soc or config.MAX_SOC_PERCENT
        min_soc = battery_min_soc or config.MIN_SOC_PERCENT
        
        # Determine charge threshold based on time of day
        charge_threshold = self.charge_price_threshold
        if timestamp is not None:
            hour = timestamp.hour
            # Solar window: 10 AM - 2 PM (10 <= hour <= 14)
            if not (10 <= hour <= 14):
                # Outside solar window: stricter condition
                charge_threshold = self.charge_price_threshold * 0.8
        
        # Rule 1: CHARGE if price is at or below charge threshold
        if price_per_kwh <= charge_threshold:
            if battery_soc_percent < max_soc:
                return Decision(
                    action=Action.CHARGE,
                    reason="Price at or below charge threshold",
                    energy_kwh=0.0  # Will be calculated based on capacity
                )
            else:
                return Decision(
                    action=Action.HOLD,
                    reason="Battery at max SoC",
                )
        
        # Rule 2: EXPORT if price is at or above export threshold
        if price_per_kwh >= self.export_price_threshold:
            if battery_soc_percent > min_soc:
                return Decision(
                    action=Action.EXPORT,
                    reason="Price at or above export threshold",
                    energy_kwh=0.0  # Will be calculated based on capacity
                )
            else:
                return Decision(
                    action=Action.HOLD,
                    reason="Battery below min SoC",
                )
        
        # Rule 3: HOLD otherwise
        return Decision(
            action=Action.HOLD,
            reason="No price signal",
        )
    
    def calculate_energy_amount(
        self,
        decision: Decision,
        battery_capacity_kwh: float,
        interval_hours: float = None,
        price_per_kwh: float = None,
        export_threshold: float = None,
        battery_soc_percent: float = None,
        battery_max_soc_percent: float = None,
    ) -> float:
        """Calculate the amount of energy to charge or discharge.
        
        Args:
            decision: The decision object.
            battery_capacity_kwh: Battery capacity in kWh.
            interval_hours: Time interval in hours.
            price_per_kwh: Current price per kWh (for export scaling).
            export_threshold: Export threshold (for strength calculation).
            battery_soc_percent: Current battery SoC in % (for SoC-based adjustment).
            battery_max_soc_percent: Maximum battery SoC in % (for SoC ratio).
            
        Returns:
            Amount of energy in kWh.
        """
        if decision.action == Action.HOLD:
            return 0.0
        
        # Full cycle amount (between min and max SoC)
        usable_capacity = battery_capacity_kwh * 0.75  # 95% - 20% = 75%
        
        if decision.action == Action.EXPORT and price_per_kwh is not None and export_threshold is not None:
            # Compute price strength
            strength = price_per_kwh / export_threshold
            
            # Define export fraction based on price strength
            if strength >= 1.5:
                export_fraction = 1.0
            elif strength >= 1.2:
                export_fraction = 0.5
            else:
                export_fraction = 0.2
            
            # Adjust export fraction based on battery SoC
            if battery_soc_percent is not None and battery_max_soc_percent is not None:
                soc_ratio = battery_soc_percent / battery_max_soc_percent
                
                if soc_ratio > 0.8:
                    export_fraction += 0.2
                elif soc_ratio < 0.4:
                    export_fraction -= 0.1
                
                # Clamp between 0.1 and 1.0
                export_fraction = max(0.1, min(1.0, export_fraction))
            
            usable_capacity *= export_fraction
        
        if interval_hours and interval_hours > 0:
            # Limit by power
            max_power_kw = config.MAX_CHARGE_KW if decision.action == Action.CHARGE else config.MAX_DISCHARGE_KW
            max_power_kwh = max_power_kw * interval_hours
            return min(usable_capacity, max_power_kwh)
        
        return usable_capacity


def get_action(
    price: float,
    soc_percent: float,
    price_history: Optional[List[float]] = None,
    charge_threshold: float = None,
    export_threshold: float = None,
    max_soc: float = None,
    min_soc: float = None,
    window_size: int = 288,
    export_percentile: float = 0.95,
    timestamp: datetime = None,
) -> str:
    """Get the action (CHARGE, HOLD, or EXPORT) based on price and battery SoC.
    
    Logic:
    - If price <= CHARGE_THRESHOLD and soc < MAX_SOC → CHARGE
    - Elif price >= DYNAMIC_EXPORT_THRESHOLD and soc > MIN_SOC → EXPORT
    - Else → HOLD
    
    The dynamic export threshold is the 95th percentile of prices over the last
    288 intervals (1 day). Falls back to config threshold if insufficient history.
    
    Time-of-day bias: Outside solar window (10-14), charge threshold is stricter (0.8x).
    
    Args:
        price: Current price in $/kWh.
        soc_percent: Current battery SoC in %.
        price_history: List of historical prices for dynamic threshold calculation.
        charge_threshold: Price threshold to charge (default from config).
        export_threshold: Fallback export threshold (default from config).
        max_soc: Maximum SoC limit (default from config).
        min_soc: Minimum SoC limit (default from config).
        window_size: Number of intervals for rolling window (default 288 = 1 day).
        export_percentile: Percentile for export threshold (default 0.95 = 95th).
        timestamp: Timestamp for time-of-day bias (optional).
    
    Returns:
        Action string: CHARGE, HOLD, or EXPORT.
    """
    charge_threshold = charge_threshold or config.CHARGE_PRICE_THRESHOLD
    static_export_threshold = export_threshold or config.EXPORT_PRICE_THRESHOLD
    max_soc = max_soc or config.MAX_SOC_PERCENT
    min_soc = min_soc or config.MIN_SOC_PERCENT
    
    # Determine effective charge threshold based on time of day
    effective_charge_threshold = charge_threshold
    if timestamp is not None:
        hour = timestamp.hour
        # Solar window: 10 AM - 2 PM (10 <= hour <= 14)
        if not (10 <= hour <= 14):
            # Outside solar window: stricter condition
            effective_charge_threshold = charge_threshold * 0.8
    
    # Calculate dynamic export threshold based on rolling percentile
    dynamic_export_threshold = static_export_threshold
    if price_history is not None and len(price_history) >= window_size:
        # Use percentile of last window_size prices
        recent_prices = price_history[-window_size:]
        dynamic_export_threshold = np.percentile(recent_prices, export_percentile * 100)
    
    # Rule 1: CHARGE if price <= threshold and SoC < max
    if price <= effective_charge_threshold and soc_percent < max_soc:
        return Action.CHARGE

    # Rule 2: EXPORT if price >= dynamic threshold and SoC > min
    if price >= dynamic_export_threshold and soc_percent > min_soc:
        return Action.EXPORT

    # Rule 3: HOLD otherwise
    return Action.HOLD