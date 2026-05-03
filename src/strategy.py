"""Arbitrage strategy for battery charging/discharging decisions."""

from dataclasses import dataclass
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
    ) -> Decision:
        """Make a decision based on current price and battery state.
        
        Args:
            price_per_kwh: Current electricity price in $/kWh.
            battery_soc_percent: Current battery state of charge in %.
            battery_max_soc: Maximum SoC limit (default from config).
            battery_min_soc: Minimum SoC limit (default from config).
            
        Returns:
            Decision object with action and reason.
        """
        max_soc = battery_max_soc or config.MAX_SOC_PERCENT
        min_soc = battery_min_soc or config.MIN_SOC_PERCENT
        
        # Rule 1: CHARGE if price is at or below charge threshold
        if price_per_kwh <= self.charge_price_threshold:
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
    ) -> float:
        """Calculate the amount of energy to charge or discharge.
        
        Args:
            decision: The decision object.
            battery_capacity_kwh: Battery capacity in kWh.
            interval_hours: Time interval in hours.
            
        Returns:
            Amount of energy in kWh.
        """
        if decision.action == Action.HOLD:
            return 0.0
        
        # Full cycle amount (between min and max SoC)
        usable_capacity = battery_capacity_kwh * 0.75  # 95% - 20% = 75%
        
        if interval_hours and interval_hours > 0:
            # Limit by power
            max_power_kwh = config.MAX_CHARGE_KW * interval_hours
            return min(usable_capacity, max_power_kwh)
        
        return usable_capacity


def get_action(
    price: float,
    soc_percent: float,
    charge_threshold: float = None,
    export_threshold: float = None,
    max_soc: float = None,
    min_soc: float = None,
) -> str:
    """Get the action (CHARGE, HOLD, or EXPORT) based on price and battery SoC.
    
    Logic:
    - If price <= CHARGE_THRESHOLD and soc < MAX_SOC → CHARGE
    - Elif price >= EXPORT_THRESHOLD and soc > MIN_SOC → EXPORT
    - Else → HOLD
    
    Args:
        price: Current price in $/kWh.
        soc_percent: Current battery SoC in %.
        charge_threshold: Price threshold to charge (default from config).
        export_threshold: Price threshold to export (default from config).
        max_soc: Maximum SoC limit (default from config).
        min_soc: Minimum SoC limit (default from config).
    
    Returns:
        Action string: CHARGE, HOLD, or EXPORT.
    """
    charge_threshold = charge_threshold or config.CHARGE_PRICE_THRESHOLD
    export_threshold = export_threshold or config.EXPORT_PRICE_THRESHOLD
    max_soc = max_soc or config.MAX_SOC_PERCENT
    min_soc = min_soc or config.MIN_SOC_PERCENT
    
    # Rule 1: CHARGE if price <= threshold and SoC < max
    if price <= charge_threshold and soc_percent < max_soc:
        return Action.CHARGE
    
    # Rule 2: EXPORT if price >= threshold and SoC > min
    if price >= export_threshold and soc_percent > min_soc:
        return Action.EXPORT
    
    # Rule 3: HOLD otherwise
    return Action.HOLD