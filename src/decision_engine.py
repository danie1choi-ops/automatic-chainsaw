"""Decision engine for energy arbitrage."""

from dataclasses import dataclass
from src.battery import BatteryState
from src import config


class Action:
    """Possible actions for the energy arbitrage controller."""
    CHARGE = "CHARGE"
    HOLD = "HOLD"
    EXPORT = "EXPORT"


# Reason codes
class Reason:
    CHEAP_IMPORT = "Cheap import price"
    NEGATIVE_IMPORT = "Negative import price"
    EXPORT_ABOVE_THRESHOLD = "Export price above threshold"
    BATTERY_BELOW_RESERVE = "Battery below reserve SoC"
    BATTERY_FULL = "Battery already full"
    NO_PRICE_SIGNAL = "No price signal"


@dataclass
class DecisionResult:
    """Result of a decision including action and reason."""
    action: str
    reason: str


def get_reserve_soc(is_night: bool) -> float:
    """Get the reserve state of charge based on time of day.
    
    Args:
        is_night: Whether it's currently night time.
        
    Returns:
        Reserve SoC percentage.
    """
    return config.NIGHT_RESERVE_SOC if is_night else config.DAY_RESERVE_SOC


def decide(
    import_price: float,
    export_price: float,
    battery_soc: float,
    is_night: bool = False
) -> DecisionResult:
    """Decide the action based on prices and battery state.
    
    Args:
        import_price: Current import price in $/kWh.
        export_price: Current export price in $/kWh.
        battery_soc: Battery state of charge in percentage.
        is_night: Whether it's currently night time.
        
    Returns:
        DecisionResult with action and reason.
    """
    battery = BatteryState(soc=battery_soc)
    reserve_soc = get_reserve_soc(is_night)
    
    # Rule 1: CHARGE if import price is negative and battery SoC < MAX_CHARGE_SOC
    if import_price < 0 and battery.can_charge():
        return DecisionResult(action=Action.CHARGE, reason=Reason.NEGATIVE_IMPORT)
    
    # Rule 2: CHARGE if import price <= CHARGE_PRICE_THRESHOLD and battery SoC < MAX_CHARGE_SOC
    if import_price <= config.CHARGE_PRICE_THRESHOLD and battery.can_charge():
        return DecisionResult(action=Action.CHARGE, reason=Reason.CHEAP_IMPORT)
    
    # Rule 3: EXPORT if export price >= EXPORT_PRICE_THRESHOLD and battery SoC > reserve SoC
    if export_price >= config.EXPORT_PRICE_THRESHOLD and battery.can_export(reserve_soc):
        return DecisionResult(action=Action.EXPORT, reason=Reason.EXPORT_ABOVE_THRESHOLD)
    
    # Rule 4: HOLD - determine specific reason
    if not battery.can_charge():
        return DecisionResult(action=Action.HOLD, reason=Reason.BATTERY_FULL)
    if not battery.can_export(reserve_soc):
        return DecisionResult(action=Action.HOLD, reason=Reason.BATTERY_BELOW_RESERVE)
    
    # Default HOLD
    return DecisionResult(action=Action.HOLD, reason=Reason.NO_PRICE_SIGNAL)