"""Unit tests for the battery model."""

import pytest
from src.battery_model import BatteryModel
from src import config


class TestBatteryModel:
    """Test cases for the battery model."""
    
    def test_battery_initial_soc(self):
        """Test that battery starts at initial SoC."""
        battery = BatteryModel()
        assert battery.soc_percent == config.INITIAL_SOC_PERCENT
    
    def test_battery_cannot_charge_above_max_soc(self):
        """Test that battery cannot charge above max SoC."""
        battery = BatteryModel()
        battery.soc_percent = 94  # Near max
        
        # Try to charge more than available capacity
        result = battery.charge(100.0)  # Try to charge way too much
        
        # Should only charge up to max SoC
        assert battery.soc_percent <= config.MAX_SOC_PERCENT
    
    def test_battery_cannot_discharge_below_min_soc(self):
        """Test that battery cannot discharge below min SoC."""
        battery = BatteryModel()
        battery.soc_percent = 25  # Near min
        
        # Try to discharge more than available
        result = battery.discharge(100.0)  # Try to discharge way too much
        
        # Should only discharge down to min SoC
        assert battery.soc_percent >= config.MIN_SOC_PERCENT
    
    def test_battery_energy_stored(self):
        """Test that energy stored calculation is correct."""
        battery = BatteryModel()
        battery.soc_percent = 50
        
        expected_energy = (50 / 100) * config.BATTERY_CAPACITY_KWH
        assert abs(battery.energy_stored_kwh - expected_energy) < 0.01
    
    def test_battery_can_charge(self):
        """Test can_charge method."""
        battery = BatteryModel()
        battery.soc_percent = 50
        
        # Should be able to charge
        assert battery.can_charge(1.0) is True
        
        # At max SoC, should not be able to charge
        battery.soc_percent = 95
        assert battery.can_charge(1.0) is False
    
    def test_battery_can_discharge(self):
        """Test can_discharge method."""
        battery = BatteryModel()
        battery.soc_percent = 50
        
        # Should be able to discharge
        assert battery.can_discharge(1.0) is True
        
        # At min SoC, should not be able to discharge
        battery.soc_percent = 20
        assert battery.can_discharge(1.0) is False
    
    def test_battery_energy_constraints(self):
        """Test that battery respects energy constraints."""
        battery = BatteryModel()
        # Battery should be initialized to initial SoC
        assert battery.soc_percent == config.INITIAL_SOC_PERCENT
        # Energy stored should equal SoC percentage
        expected_energy = (config.INITIAL_SOC_PERCENT / 100) * config.BATTERY_CAPACITY_KWH
        assert abs(battery.energy_stored_kwh - expected_energy) < 0.01
    
    def test_battery_usable_capacity(self):
        """Test usable capacity calculation."""
        battery = BatteryModel()
        
        usable = battery.usable_energy_kwh
        expected = ((config.MAX_SOC_PERCENT - config.MIN_SOC_PERCENT) / 100) * config.BATTERY_CAPACITY_KWH
        
        assert abs(usable - expected) < 0.01