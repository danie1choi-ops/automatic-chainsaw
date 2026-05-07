"""Tests for tariff scenario modelling."""

import unittest
from datetime import datetime, timedelta
from src.tariff_scenarios import (
    TariffScenario,
    TARIFF_SCENARIOS,
    run_scenario,
    run_all_scenarios,
)
from src.data_loader import PricePoint
from src import config


class TestTariffScenario(unittest.TestCase):
    """Test tariff scenario functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create 24 hours of price data (5-min intervals)
        self.price_data = []
        base_time = datetime(2024, 5, 1, 0, 0, 0)
        
        # Morning low prices (cheap solar soak)
        for i in range(0, 6 * 12):  # 0-6 AM
            time = base_time + timedelta(minutes=i * 5)
            price = 0.05 + (i % 5) * 0.01  # $0.05-0.09/kWh
            self.price_data.append(PricePoint(time, "QLD1", price))
        
        # Midday moderate prices
        for i in range(6 * 12, 12 * 12):  # 6-12 noon
            time = base_time + timedelta(minutes=i * 5)
            price = 0.15 + (i % 10) * 0.01  # $0.15-0.25/kWh
            self.price_data.append(PricePoint(time, "QLD1", price))
        
        # Afternoon peak prices
        for i in range(12 * 12, 18 * 12):  # 12-6 PM
            time = base_time + timedelta(minutes=i * 5)
            price = 0.25 + (i % 15) * 0.01  # $0.25-0.40/kWh
            self.price_data.append(PricePoint(time, "QLD1", price))
        
        # Evening drop
        for i in range(18 * 12, 24 * 12):  # 6 PM-12 AM
            time = base_time + timedelta(minutes=i * 5)
            price = 0.12 + (i % 8) * 0.01  # $0.12-0.20/kWh
            self.price_data.append(PricePoint(time, "QLD1", price))
    
    def test_scenario_definitions(self):
        """Test that all 4 scenarios are defined."""
        self.assertEqual(len(TARIFF_SCENARIOS), 4)
        
        expected_names = [
            "Wholesale Arbitrage Mode",
            "Retail Import/Feed-in Tariff Mode",
            "Existing Battery Marginal Mode",
            "New Battery Full-Cost Mode",
        ]
        
        actual_names = [s.name for s in TARIFF_SCENARIOS]
        for name in expected_names:
            self.assertIn(name, actual_names)
    
    def test_scenario_economics(self):
        """Test that scenarios are economically sensible."""
        for scenario in TARIFF_SCENARIOS:
            # Prices should be positive
            self.assertGreater(scenario.import_price_per_kwh, 0)
            self.assertGreater(scenario.export_price_per_kwh, 0)
            
            # Note: Import price may be > export price in retail scenarios
            # (where there's limited arbitrage opportunity)
    
    def test_run_scenario_basic(self):
        """Test running a basic scenario."""
        scenario = TARIFF_SCENARIOS[0]  # Wholesale mode
        result = run_scenario(scenario, self.price_data)
        
        # Check result structure
        self.assertIsNotNone(result.scenario)
        self.assertGreater(result.period_days, 0)
        self.assertGreaterEqual(result.total_charged_kwh, 0)
        self.assertGreaterEqual(result.total_exported_kwh, 0)
        self.assertGreaterEqual(result.equivalent_cycles, 0)
    
    def test_gross_profit_positive(self):
        """Test that gross profit is positive in profitable scenarios."""
        # Wholesale mode should be profitable on this price data
        scenario = TARIFF_SCENARIOS[0]
        result = run_scenario(scenario, self.price_data)
        
        # Should have some arbitrage opportunity
        self.assertGreaterEqual(result.gross_profit, 0)
    
    def test_degradation_cost_calculation(self):
        """Test that degradation cost is calculated correctly."""
        scenario = TARIFF_SCENARIOS[0]
        result = run_scenario(scenario, self.price_data)
        
        # Degradation should scale with energy moved
        expected_degradation = (
            (result.total_charged_kwh + result.total_exported_kwh) *
            config.DEGRADATION_COST_PER_KWH
        )
        
        self.assertAlmostEqual(
            result.degradation_cost,
            expected_degradation,
            places=2
        )
    
    def test_net_marginal_profit(self):
        """Test that net marginal profit = gross profit - degradation."""
        scenario = TARIFF_SCENARIOS[0]
        result = run_scenario(scenario, self.price_data)
        
        expected_net = result.gross_profit - result.degradation_cost
        self.assertAlmostEqual(
            result.net_marginal_profit,
            expected_net,
            places=4
        )
    
    def test_annualised_profit(self):
        """Test annualisation of profit."""
        scenario = TARIFF_SCENARIOS[0]
        result = run_scenario(scenario, self.price_data)
        
        # Annualised should scale by 365/period_days
        expected_annual = result.net_marginal_profit * (365 / result.period_days)
        self.assertAlmostEqual(
            result.annualised_profit,
            expected_annual,
            places=4
        )
    
    def test_simple_payback_calculation(self):
        """Test simple payback calculation."""
        scenario = TARIFF_SCENARIOS[0]  # Full cost scenario
        result = run_scenario(scenario, self.price_data)
        
        # Only test if payback is possible
        if result.simple_payback_years is not None:
            system_cost = scenario.system_cost_override or config.TOTAL_BATTERY_SYSTEM_COST
            expected_payback = system_cost / result.annualised_profit
            self.assertAlmostEqual(
                result.simple_payback_years,
                expected_payback,
                places=4
            )
    
    def test_marginal_mode_no_payback(self):
        """Test that marginal mode has no payback (already owns battery)."""
        scenario = TARIFF_SCENARIOS[2]  # Existing battery mode
        self.assertEqual(scenario.system_cost_override, 0.0)
        result = run_scenario(scenario, self.price_data)
        
        # Should have no payback since there's no capital cost
        self.assertIsNone(result.simple_payback_years)
    
    def test_run_all_scenarios(self):
        """Test running all scenarios."""
        results = run_all_scenarios(self.price_data)
        
        # Should have 4 results
        self.assertEqual(len(results), 4)
        
        # Check all scenarios are present
        for scenario in TARIFF_SCENARIOS:
            self.assertIn(scenario.name, results)
    
    def test_scenario_consistency(self):
        """Test that scenarios produce consistent results."""
        scenario = TARIFF_SCENARIOS[0]
        result1 = run_scenario(scenario, self.price_data)
        result2 = run_scenario(scenario, self.price_data)
        
        # Same inputs should give same outputs
        self.assertEqual(result1.gross_profit, result2.gross_profit)
        self.assertEqual(result1.degradation_cost, result2.degradation_cost)
        self.assertEqual(result1.net_marginal_profit, result2.net_marginal_profit)


class TestScenarioEconomics(unittest.TestCase):
    """Test economic scenarios."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic price data with clear arbitrage
        self.price_data = []
        base_time = datetime(2024, 5, 1, 0, 0, 0)
        
        # Simple oscillating prices for clear arbitrage
        for i in range(288):  # 24 hours
            time = base_time + timedelta(minutes=i * 5)
            # Oscillate between 0.10 and 0.30
            price = 0.10 if i % 2 == 0 else 0.30
            self.price_data.append(PricePoint(time, "QLD1", price))
    
    def test_wholesale_vs_retail(self):
        """Compare wholesale and retail scenarios."""
        wholesale = TARIFF_SCENARIOS[0]
        retail = TARIFF_SCENARIOS[1]
        
        wholesale_result = run_scenario(wholesale, self.price_data)
        retail_result = run_scenario(retail, self.price_data)
        
        # Both scenarios should run without error
        self.assertIsNotNone(wholesale_result)
        self.assertIsNotNone(retail_result)
    
    def test_marginal_vs_full_cost(self):
        """Compare marginal (existing) vs full-cost (new) scenarios."""
        marginal = TARIFF_SCENARIOS[2]
        full_cost = TARIFF_SCENARIOS[3]
        
        marginal_result = run_scenario(marginal, self.price_data)
        full_cost_result = run_scenario(full_cost, self.price_data)
        
        # Both should run without error
        self.assertIsNotNone(marginal_result)
        self.assertIsNotNone(full_cost_result)
        
        # But payback should be None for marginal (no capital cost)
        self.assertIsNone(marginal_result.simple_payback_years)
        # full_cost_result.simple_payback_years could be None if unprofitable


if __name__ == '__main__':
    unittest.main()
