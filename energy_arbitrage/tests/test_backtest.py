"""Unit tests for the backtest engine."""

import pytest
from datetime import datetime
from src.data_loader import PricePoint
from src.backtest import run_backtest
from src import config


class TestBacktest:
    """Test cases for the backtest engine."""
    
    def test_backtest_produces_non_empty_output(self, tmp_path):
        """Test that backtest produces non-empty output."""
        # Create test price data
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, i), region="QLD1", price_per_kwh=0.04)
            for i in range(0, 60, 5)  # 12 intervals
        ]
        
        # Run backtest
        results = run_backtest(price_data)
        
        # Check results
        assert results is not None
        assert 'num_intervals' in results
        assert results['num_intervals'] == 12
    
    def test_backtest_calculates_net_profit(self):
        """Test that backtest calculates net profit."""
        # Create test price data with varying prices
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, i*5), region="QLD1", price_per_kwh=0.04)
            for i in range(12)
        ]
        
        # Run backtest
        results = run_backtest(price_data)
        
        # Check profit calculations
        assert 'total_gross_profit' in results
        assert 'total_degradation_cost' in results
        assert 'net_profit' in results
    
    def test_backtest_with_charge_and_export(self):
        """Test backtest with both charging and exporting."""
        # Create price data that triggers both charge and export
        price_data = [
            # Cheap prices - should charge
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 0), region="QLD1", price_per_kwh=0.04),
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 5), region="QLD1", price_per_kwh=0.03),
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 10), region="QLD1", price_per_kwh=0.02),
            # Normal prices - should hold
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 15), region="QLD1", price_per_kwh=0.15),
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 20), region="QLD1", price_per_kwh=0.18),
            # Expensive prices - should export
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 25), region="QLD1", price_per_kwh=0.35),
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 30), region="QLD1", price_per_kwh=0.40),
            PricePoint(timestamp=datetime(2026, 5, 1, 0, 35), region="QLD1", price_per_kwh=0.45),
        ]
        
        # Run backtest
        results = run_backtest(price_data)
        
        # Check that we have some charged energy at minimum
        assert results['total_charged_kwh'] > 0
    
    def test_backtest_equivalent_cycles(self):
        """Test that equivalent cycles are calculated."""
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, (i % 12)*5), region="QLD1", price_per_kwh=0.04)
            for i in range(24)  # Multiple hours of data
        ]
        
        results = run_backtest(price_data)
        
        # Check equivalent cycles calculation
        assert 'equivalent_cycles' in results
        assert results['equivalent_cycles'] >= 0
    
    def test_backtest_ending_soc(self):
        """Test that ending SoC is tracked."""
        price_data = [
            PricePoint(timestamp=datetime(2026, 5, 1, 0, i*5), region="QLD1", price_per_kwh=0.04)
            for i in range(12)
        ]
        
        results = run_backtest(price_data)
        
        # Check ending SoC
        assert 'ending_soc' in results
        assert 0 <= results['ending_soc'] <= 100