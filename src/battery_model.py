"""Battery model for simulating energy storage."""

from dataclasses import dataclass
from src import config


@dataclass
class BatteryState:
    """Current state of the battery."""
    soc_percent: float  # State of charge in percentage
    energy_stored_kwh: float  # Energy currently stored in kWh


class BatteryModel:
    """Simulates a home battery energy storage system."""
    
    def __init__(
        self,
        capacity_kwh: float = None,
        max_charge_kw: float = None,
        max_discharge_kw: float = None,
        min_soc_percent: float = None,
        max_soc_percent: float = None,
        round_trip_efficiency: float = None,
        initial_soc_percent: float = None,
    ):
        """Initialize the battery model.
        
        Args:
            capacity_kwh: Total battery capacity in kWh.
            max_charge_kw: Maximum charge power in kW.
            max_discharge_kw: Maximum discharge power in kW.
            min_soc_percent: Minimum SoC percentage.
            max_soc_percent: Maximum SoC percentage.
            round_trip_efficiency: Round trip efficiency (0-1).
            initial_soc_percent: Initial SoC percentage.
        """
        self.capacity_kwh = capacity_kwh or config.BATTERY_CAPACITY_KWH
        self.max_charge_kw = max_charge_kw or config.MAX_CHARGE_KW
        self.max_discharge_kw = max_discharge_kw or config.MAX_DISCHARGE_KW
        self.min_soc_percent = min_soc_percent or config.MIN_SOC_PERCENT
        self.max_soc_percent = max_soc_percent or config.MAX_SOC_PERCENT
        self.round_trip_efficiency = round_trip_efficiency or config.ROUND_TRIP_EFFICIENCY
        self.initial_soc_percent = initial_soc_percent or config.INITIAL_SOC_PERCENT
        
        # Initialize state
        self.soc_percent = self.initial_soc_percent
        self._reset()
    
    def _clamp_soc(self):
        """Clamp SoC to valid range [MIN_SOC, MAX_SOC]."""
        self.soc_percent = max(
            self.min_soc_percent,
            min(self.max_soc_percent, self.soc_percent)
        )
    
    def _reset(self):
        """Reset battery to initial state."""
        self.soc_percent = self.initial_soc_percent
    
    @property
    def energy_stored_kwh(self) -> float:
        """Get current energy stored in kWh."""
        return (self.soc_percent / 100) * self.capacity_kwh
    
    @property
    def usable_energy_kwh(self) -> float:
        """Get usable energy between min and max SoC."""
        usable_percent = self.max_soc_percent - self.min_soc_percent
        return (usable_percent / 100) * self.capacity_kwh
    
    @property
    def min_energy_kwh(self) -> float:
        """Get minimum energy in kWh (based on min SoC)."""
        return (self.min_soc_percent / 100) * self.capacity_kwh
    
    @property
    def max_energy_kwh(self) -> float:
        """Get maximum energy in kWh (based on max SoC)."""
        return (self.max_soc_percent / 100) * self.capacity_kwh
    
    def can_charge(self, amount_kwh: float) -> bool:
        """Check if battery can accept charge.
        
        Args:
            amount_kwh: Amount of energy to charge in kWh.
            
        Returns:
            True if battery can accept the charge.
        """
        max_add = self.max_energy_kwh - self.energy_stored_kwh
        return amount_kwh <= max_add
    
    def can_discharge(self, amount_kwh: float) -> bool:
        """Check if battery can provide discharge.
        
        Args:
            amount_kwh: Amount of energy to discharge in kWh.
            
        Returns:
            True if battery can provide the discharge.
        """
        min_usable = self.energy_stored_kwh - self.min_energy_kwh
        return amount_kwh <= min_usable
    
    def charge(self, amount_kwh: float, interval_hours: float = None) -> float:
        """Charge the battery by a given amount of energy.
        
        Args:
            amount_kwh: Amount of energy to charge in kWh.
            interval_hours: Time interval for the charge (for power limiting).
            
        Returns:
            Actual amount of energy charged in kWh.
        """
        # Cannot charge if already at max SoC
        if self.soc_percent >= self.max_soc_percent:
            return 0.0
        
        # Limit by max energy capacity
        max_add = self.max_energy_kwh - self.energy_stored_kwh
        actual_kwh = min(amount_kwh, max_add)
        
        # Limit by power if interval is specified
        if interval_hours and interval_hours > 0:
            max_power_kwh = self.max_charge_kw * interval_hours
            actual_kwh = min(actual_kwh, max_power_kwh)
        
        # Update state: simply add the energy to battery
        if actual_kwh > 0:
            new_energy = self.energy_stored_kwh + actual_kwh
            self.soc_percent = (new_energy / self.capacity_kwh) * 100
        
        # Clamp to ensure SoC stays within bounds
        self._clamp_soc()
        
        return actual_kwh
    
    def discharge(self, amount_kwh: float, interval_hours: float = None) -> float:
        """Discharge the battery by a given amount of energy.
        
        Args:
            amount_kwh: Amount of energy to discharge in kWh.
            interval_hours: Time interval for the discharge (for power limiting).
            
        Returns:
            Actual amount of energy discharged in kWh.
        """
        # Cannot discharge if already at or below min SoC
        if self.soc_percent <= self.min_soc_percent:
            return 0.0
        
        # Calculate max discharge based on maintaining MIN_SOC
        max_discharge_energy = self.energy_stored_kwh - self.min_energy_kwh
        
        # If max_discharge_energy is too small, don't discharge
        if max_discharge_energy <= 0:
            return 0.0
        
        actual_kwh = min(amount_kwh, max_discharge_energy)
        
        # Limit by power if interval is specified
        if interval_hours and interval_hours > 0:
            max_power_kwh = self.max_discharge_kw * interval_hours
            actual_kwh = min(actual_kwh, max_power_kwh)
        
        # Update state: subtract the discharged energy
        if actual_kwh > 0:
            new_energy = self.energy_stored_kwh - actual_kwh
            self.soc_percent = (new_energy / self.capacity_kwh) * 100
        
        # Clamp to ensure SoC stays within bounds
        self._clamp_soc()
        
        return actual_kwh
    
    def get_state(self) -> BatteryState:
        """Get current battery state.
        
        Returns:
            BatteryState object.
        """
        return BatteryState(
            soc_percent=self.soc_percent,
            energy_stored_kwh=self.energy_stored_kwh
        )