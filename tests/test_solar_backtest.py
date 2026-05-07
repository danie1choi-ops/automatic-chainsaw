"""Tests for solar backtest functionality."""

import unittest
from datetime import datetime, timedelta
from src.solar_backtest import run_solar_backtest
from src.solar_load_model import (
    SolarProfile,
    HouseholdLoad,
    DEFAULT_SOLAR_PROFILE,
    DEFAULT_HOUSEHOLD_LOAD,
)
from src.data_loader import PricePoint


class TestSolarBacktest(unittest.TestCase):
    """Test solar backtest functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create 24 hours of synthetic price data
        self.price_data = []
        base_time = datetime(2024, 5, 1, 0, 0, 0)
        
        for i in range(24 * 12):  # 24 hours, 5-min intervals
            time = base_time + timedelta(minutes=i * 5)
            # Oscillate between low (night) and high (day)
            hour = time.hour
            if 6 <= hour <= 18:
                price = 0.20 + 0.10 * (1 - (hour - 12) ** 2 / 36)
            else:
                price = 0.10
            self.price_data.append(PricePoint(time, "QLD1", price))
    
    def test_solar_backtest_runs(self):
        """Test that solar backtest runs without error."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        self.assertIsNotNone(results)
        self.assertIsNotNone(solar_load_results)
    
    def test_solar_generation_tracked(self):
        """Test that solar generation is tracked."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        self.assertGreater(solar_load_results.total_solar_generated_kwh, 0)
    
    def test_household_demand_tracked(self):
        """Test that household demand is tracked."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        self.assertGreater(solar_load_results.total_household_demand_kwh, 0)
    
    def test_grid_import_less_than_demand(self):
        """Test that grid import is less than demand (due to solar)."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        self.assertLess(
            solar_load_results.total_grid_import_kwh,
            solar_load_results.total_household_demand_kwh
        )
    
    def test_solar_savings_positive(self):
        """Test that solar provides cost savings."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        self.assertGreater(solar_load_results.solar_savings, 0)
    
    def test_solar_self_consumption(self):
        """Test that solar is self-consumed."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        
        # Self-consumed should be less than or equal to generated
        self.assertLessEqual(
            solar_load_results.total_solar_self_consumed_kwh,
            solar_load_results.total_solar_generated_kwh
        )
        
        # Self-consumed + exported should equal generated
        total = (
            solar_load_results.total_solar_self_consumed_kwh +
            solar_load_results.total_solar_exported_kwh
        )
        self.assertAlmostEqual(
            total,
            solar_load_results.total_solar_generated_kwh,
            places=1
        )
    
    def test_battery_discharge_to_load(self):
        """Test that battery discharges to meet load."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        
        # Battery should discharge some energy to load
        self.assertGreater(
            solar_load_results.total_battery_discharged_to_load_kwh,
            0
        )
    
    def test_energy_balance(self):
        """Test overall energy balance."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        
        # Household demand should be met by: solar + battery + grid
        # Note: Battery can charge from both solar and arbitrage,
        # so the balance is complex when arbitrage is active
        solar_to_load = min(
            solar_load_results.total_solar_generated_kwh,
            solar_load_results.total_household_demand_kwh
        )
        battery_discharge = solar_load_results.total_battery_discharged_to_load_kwh
        grid_import = solar_load_results.total_grid_import_kwh
        demand = solar_load_results.total_household_demand_kwh
        
        # Demand + any battery charging from arbitrage should be met by solar + battery discharge + grid
        # This allows for battery arbitrage charging
        total_sources = solar_to_load + battery_discharge + grid_import
        
        # Should approximately meet or exceed demand
        # (arbitrage can cause battery to charge/discharge extra)
        self.assertGreater(total_sources, demand * 0.9)
    
    def test_custom_solar_profile(self):
        """Test with custom solar profile."""
        custom_solar = SolarProfile(
            peak_hour=14.0,  # Different peak
            peak_power_kw=10.0,  # Higher power
            sunrise_hour=5.0,  # Earlier sunrise
            sunset_hour=19.0,  # Later sunset
        )
        
        results, solar_load_results = run_solar_backtest(
            self.price_data,
            solar_profile=custom_solar
        )
        
        # Higher peak power should mean more generation
        self.assertGreater(
            solar_load_results.total_solar_generated_kwh,
            20.0  # Should be higher than default 8kW
        )
    
    def test_grid_import_cost_calculation(self):
        """Test that grid import costs are calculated."""
        results, solar_load_results = run_solar_backtest(
            self.price_data,
            import_price_per_kwh=0.30
        )
        
        # Cost without solar should be higher than with solar
        self.assertGreater(
            solar_load_results.grid_import_cost_without_solar,
            solar_load_results.grid_import_cost_with_solar
        )
        
        # Solar savings should be positive
        self.assertGreater(solar_load_results.solar_savings, 0)
    
    def test_arbitrage_tracked_separately(self):
        """Test that arbitrage profit is tracked."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        
        # Arbitrage profit should exist (could be positive or negative)
        self.assertIsNotNone(solar_load_results.arbitrage_profit_on_top)
    
    def test_total_benefit(self):
        """Test that total benefit combines solar savings and arbitrage."""
        results, solar_load_results = run_solar_backtest(self.price_data)
        
        # Total benefit should be sum of solar savings and arbitrage
        expected_total = (
            solar_load_results.solar_savings +
            solar_load_results.arbitrage_profit_on_top
        )
        self.assertAlmostEqual(
            solar_load_results.total_benefit,
            expected_total,
            places=2
        )
    
    def test_different_import_prices(self):
        """Test that different import prices affect savings."""
        results_low, solar_load_results_low = run_solar_backtest(
            self.price_data,
            import_price_per_kwh=0.20
        )
        
        results_high, solar_load_results_high = run_solar_backtest(
            self.price_data,
            import_price_per_kwh=0.40
        )
        
        # Higher import price should mean higher savings
        self.assertGreater(
            solar_load_results_high.solar_savings,
            solar_load_results_low.solar_savings
        )


if __name__ == '__main__':
    unittest.main()
