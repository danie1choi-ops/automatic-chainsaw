"""Tests for performance metrics and investment analysis."""

import unittest
from datetime import datetime, timedelta
from src.performance import calculate_investment_metrics
from src.data_loader import PricePoint


class TestPerformance(unittest.TestCase):
    """Test performance metrics calculations."""

    def test_annualization_exists(self):
        """Test that annualization is calculated."""
        # Create price data for 2 days
        price_data = []
        start_time = datetime(2026, 5, 1, 0, 0)
        for i in range(576):  # 2 days * 288 intervals
            timestamp = start_time + timedelta(minutes=i * 5)
            price_data.append(PricePoint(
                timestamp=timestamp,
                region="QLD1",
                price_per_kwh=0.10
            ))
        
        # Create results with a profit
        results = {
            'total_gross_profit': 10.0,
            'total_degradation_cost': 5.0,
            'net_profit': 5.0,
            'total_charged_kwh': 20.0,
            'total_exported_kwh': 15.0,
            'equivalent_cycles': 2.6,
            'ending_soc': 50.0,
            'num_intervals': 576,
        }
        
        metrics = calculate_investment_metrics(results, price_data)
        
        # Annualization should exist
        assert 'annual_net_profit' in metrics
        # Over ~2 days, profit should be annualized
        # The exact calculation depends on the actual time span
        assert metrics['annual_net_profit'] > 500  # Should be significant
        assert metrics['annual_net_profit'] < 1500  # But reasonable

    def test_payback_never_when_negative_profit(self):
        """Test that payback returns 'Never' when profit is negative."""
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 0), region="QLD1", price_per_kwh=0.10),
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 5), region="QLD1", price_per_kwh=0.10),
        ]
        
        results = {
            'total_gross_profit': 1.0,
            'total_degradation_cost': 5.0,
            'net_profit': -4.0,  # Negative profit
            'total_charged_kwh': 10.0,
            'total_exported_kwh': 5.0,
            'equivalent_cycles': 1.1,
            'ending_soc': 50.0,
            'num_intervals': 2,
        }
        
        metrics = calculate_investment_metrics(results, price_data)
        
        # Payback should be "Never" for negative profit
        assert metrics['simple_payback_years'] == "Never"

    def test_payback_returns_number_for_positive_profit(self):
        """Test that payback returns a number when profit is positive."""
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 0), region="QLD1", price_per_kwh=0.10),
            PricePoint(timestamp=datetime(2026, 5, 1, 1, 0), region="QLD1", price_per_kwh=0.10),
        ]
        
        # Over 1 hour, net profit of $1000, which annualizes to $8,760,000
        # With $17,000 system cost, payback should be about 0.002 years
        results = {
            'total_gross_profit': 1000.0,
            'total_degradation_cost': 0.0,
            'net_profit': 1000.0,  # Positive profit
            'total_charged_kwh': 100.0,
            'total_exported_kwh': 50.0,
            'equivalent_cycles': 11.0,
            'ending_soc': 50.0,
            'num_intervals': 12,
        }
        
        metrics = calculate_investment_metrics(results, price_data)
        
        # Payback should be a number
        assert isinstance(metrics['simple_payback_years'], float)
        # Payback should be positive
        assert metrics['simple_payback_years'] > 0
        # Payback should be reasonable (less than 1000 years)
        assert metrics['simple_payback_years'] < 1000

    def test_annualization_single_day(self):
        """Test annualization for exactly one day of data."""
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 0), region="QLD1", price_per_kwh=0.10),
            PricePoint(timestamp=datetime(2026, 5, 2, 0, 0), region="QLD1", price_per_kwh=0.10),
        ]
        
        results = {
            'total_gross_profit': 10.0,
            'total_degradation_cost': 5.0,
            'net_profit': 5.0,
            'total_charged_kwh': 20.0,
            'total_exported_kwh': 15.0,
            'equivalent_cycles': 2.6,
            'ending_soc': 50.0,
            'num_intervals': 2,
        }
        
        metrics = calculate_investment_metrics(results, price_data)
        
        # For 1 day of data, annualization should multiply by 365
        assert abs(metrics['annual_net_profit'] - 5.0 * 365) < 0.1

    def test_days_in_dataset_calculation(self):
        """Test that days in dataset is calculated correctly."""
        # 7 days of data
        price_data = []
        start_time = datetime(2026, 5, 1, 0, 0)
        for i in range(7 * 288):  # 7 days
            timestamp = start_time + timedelta(minutes=i * 5)
            price_data.append(PricePoint(
                timestamp=timestamp,
                region="QLD1",
                price_per_kwh=0.10
            ))
        
        results = {
            'total_gross_profit': 10.0,
            'total_degradation_cost': 5.0,
            'net_profit': 5.0,
            'total_charged_kwh': 20.0,
            'total_exported_kwh': 15.0,
            'equivalent_cycles': 2.6,
            'ending_soc': 50.0,
            'num_intervals': 7 * 288,
        }
        
        metrics = calculate_investment_metrics(results, price_data)
        
        # Days should be approximately 7
        assert abs(metrics['days_in_dataset'] - 7.0) < 0.01


if __name__ == '__main__':
    unittest.main()
