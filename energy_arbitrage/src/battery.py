"""Battery state management."""

from dataclasses import dataclass
from src import config


@dataclass
class BatteryState:
    """Represents the current state of a battery."""
    
    soc: float  # State of charge in percentage (0-100)
    
    def is_full(self) -> bool:
        """Check if battery is at full capacity."""
        return self.soc >= config.MAX_CHARGE_SOC
    
    def can_charge(self) -> bool:
        """Check if battery can accept more charge."""
        return self.soc < config.MAX_CHARGE_SOC
    
    def can_export(self, reserve_soc: float) -> bool:
        """Check if battery has enough charge to export."""
        return self.soc > reserve_soc