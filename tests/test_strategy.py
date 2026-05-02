"""Unit tests for the arbitrage strategy."""

import pytest
from src.strategy import Strategy, Action
from src import config


class TestStrategy:
    """Test cases for the arbitrage strategy."""
    
    def test_cheap_price_triggers_charge(self):
        """Test that cheap price triggers CHARGE."""
        strategy = Strategy()
        
        # Price below charge threshold
        decision = strategy.decide(
            price_per_kwh=0.04,
            battery_soc_percent=50,
        )
        
        assert decision.action == Action.CHARGE
    
    def test_negative_price_triggers_charge(self):
        """Test that negative price triggers CHARGE."""
        strategy = Strategy()
        
        # Negative price (very cheap)
        decision = strategy.decide(
            price_per_kwh=-0.05,
            battery_soc_percent=50,
        )
        
        assert decision.action == Action.CHARGE
    
    def test_high_price_triggers_export(self):
        """Test that high price triggers EXPORT."""
        strategy = Strategy()
        
        # Price above export threshold
        decision = strategy.decide(
            price_per_kwh=0.35,
            battery_soc_percent=50,
        )
        
        assert decision.action == Action.EXPORT
    
    def test_normal_price_triggers_hold(self):
        """Test that normal price triggers HOLD."""
        strategy = Strategy()
        
        # Price between thresholds
        decision = strategy.decide(
            price_per_kwh=0.15,
            battery_soc_percent=50,
        )
        
        assert decision.action == Action.HOLD
    
    def test_hold_when_battery_at_max_soc(self):
        """Test HOLD when battery is at max SoC."""
        strategy = Strategy()
        
        # Cheap price but battery at max
        decision = strategy.decide(
            price_per_kwh=0.04,
            battery_soc_percent=95,
        )
        
        assert decision.action == Action.HOLD
        assert "max" in decision.reason.lower()
    
    def test_hold_when_battery_at_min_soc(self):
        """Test HOLD when battery is at min SoC."""
        strategy = Strategy()
        
        # High price but battery at min
        decision = strategy.decide(
            price_per_kwh=0.35,
            battery_soc_percent=20,
        )
        
        assert decision.action == Action.HOLD
        assert "min" in decision.reason.lower()
    
    def test_calculate_energy_amount(self):
        """Test energy amount calculation."""
        strategy = Strategy()
        
        decision = Strategy().decide(
            price_per_kwh=0.04,
            battery_soc_percent=50,
        )
        
        energy = strategy.calculate_energy_amount(
            decision=decision,
            battery_capacity_kwh=13.5,
            interval_hours=5/60,  # 5 minutes
        )
        
        # Should be limited by power
        assert energy > 0
        assert energy <= config.MAX_CHARGE_KW * (5/60)
    
    def test_strategy_with_custom_thresholds(self):
        """Test strategy with custom thresholds."""
        strategy = Strategy(
            charge_price_threshold=0.03,
            export_price_threshold=0.25,
        )
        
        # Price 0.04 is above custom charge threshold (0.03)
        # So should not charge, but price is still below export threshold
        # and battery is not at max SoC, so should hold
        decision = strategy.decide(
            price_per_kwh=0.04,
            battery_soc_percent=50,
        )
        
        # Should hold since price is not cheap enough
        assert decision.action == Action.HOLD
        
        # Now test with price below custom threshold
        decision2 = strategy.decide(
            price_per_kwh=0.02,
            battery_soc_percent=50,
        )
        
        # Should charge with custom threshold
        assert decision2.action == Action.CHARGE