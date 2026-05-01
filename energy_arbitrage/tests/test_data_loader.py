"""Tests for data loader with multiple CSV formats."""

import unittest
import tempfile
import csv
from datetime import datetime
from pathlib import Path
from src.data_loader import load_price_data, detect_csv_format, PricePoint


class TestDataLoader(unittest.TestCase):
    """Test data loading functionality."""

    def test_load_sample_format(self):
        """Test loading the existing sample format (Format A)."""
        # Load the actual sample file
        price_data = load_price_data("data/sample_prices.csv")
        
        # Should have 288 data points
        assert len(price_data) == 288
        
        # All should be PricePoint objects
        assert all(isinstance(p, PricePoint) for p in price_data)
        
        # All should have QLD1 region
        assert all(p.region == "QLD1" for p in price_data)
        
        # Prices should be numeric and reasonable
        assert all(isinstance(p.price_per_kwh, float) for p in price_data)
        assert all(-1 < p.price_per_kwh < 100 for p in price_data)  # Reasonable range

    def test_detect_format_a(self):
        """Test format detection for sample format."""
        format_info = detect_csv_format("data/sample_prices.csv")
        
        assert format_info['timestamp'] == 'timestamp'
        assert format_info['region'] == 'region'
        assert format_info['price_per_kwh'] == 'price_per_kwh'
        assert format_info['needs_rrp_conversion'] is False

    def test_load_aemo_format(self):
        """Test loading AEMO-style format (Format B)."""
        # Create a temporary AEMO-style CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['SETTLEMENTDATE', 'REGIONID', 'RRP'])
            writer.writeheader()
            
            # Write test data (5-minute intervals, RRP in $/MWh)
            writer.writerow({
                'SETTLEMENTDATE': '2026-05-01T00:00:00',
                'REGIONID': 'QLD1',
                'RRP': '50.00'  # $50/MWh = $0.05/kWh
            })
            writer.writerow({
                'SETTLEMENTDATE': '2026-05-01T00:05:00',
                'REGIONID': 'QLD1',
                'RRP': '300.00'  # $300/MWh = $0.30/kWh
            })
            writer.writerow({
                'SETTLEMENTDATE': '2026-05-01T00:10:00',
                'REGIONID': 'QLD1',
                'RRP': '-100.00'  # -$100/MWh = -$0.10/kWh
            })
            temp_path = f.name
        
        try:
            # Load the data
            price_data = load_price_data(temp_path)
            
            # Should have 3 data points
            assert len(price_data) == 3
            
            # Check RRP conversion ($/MWh to $/kWh)
            assert abs(price_data[0].price_per_kwh - 0.05) < 0.0001
            assert abs(price_data[1].price_per_kwh - 0.30) < 0.0001
            assert abs(price_data[2].price_per_kwh - (-0.10)) < 0.0001
            
        finally:
            Path(temp_path).unlink()

    def test_aemo_format_rrp_conversion(self):
        """Test that RRP is correctly converted from $/MWh to $/kWh."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['SETTLEMENTDATE', 'REGIONID', 'RRP'])
            writer.writeheader()
            
            # Write data with known RRP values
            test_cases = [
                ('2026-05-01T00:00:00', 'QLD1', '1000', 1.0),  # $1000/MWh = $1/kWh
                ('2026-05-01T00:05:00', 'QLD1', '2500', 2.5),  # $2500/MWh = $2.5/kWh
                ('2026-05-01T00:10:00', 'QLD1', '0', 0.0),     # $0/MWh = $0/kWh
                ('2026-05-01T00:15:00', 'QLD1', '-500', -0.5), # -$500/MWh = -$0.5/kWh
            ]
            
            for ts, region, rrp, _ in test_cases:
                writer.writerow({
                    'SETTLEMENTDATE': ts,
                    'REGIONID': region,
                    'RRP': rrp
                })
            
            temp_path = f.name
        
        try:
            price_data = load_price_data(temp_path)
            
            for i, (_, _, _, expected_price) in enumerate(test_cases):
                assert abs(price_data[i].price_per_kwh - expected_price) < 0.0001
                
        finally:
            Path(temp_path).unlink()

    def test_aemo_format_region_filter(self):
        """Test that AEMO format can be filtered by region."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['SETTLEMENTDATE', 'REGIONID', 'RRP'])
            writer.writeheader()
            
            # Write data with multiple regions
            regions_data = [
                ('2026-05-01T00:00:00', 'QLD1', '100'),
                ('2026-05-01T00:05:00', 'NSW1', '150'),
                ('2026-05-01T00:10:00', 'QLD1', '120'),
                ('2026-05-01T00:15:00', 'VIC1', '200'),
                ('2026-05-01T00:20:00', 'QLD1', '110'),
            ]
            
            for ts, region, rrp in regions_data:
                writer.writerow({
                    'SETTLEMENTDATE': ts,
                    'REGIONID': region,
                    'RRP': rrp
                })
            
            temp_path = f.name
        
        try:
            # Load without filter
            price_data_all = load_price_data(temp_path)
            assert len(price_data_all) == 5
            
            # Load with QLD1 filter
            price_data_qld = load_price_data(temp_path, region_filter='QLD1')
            assert len(price_data_qld) == 3
            assert all(p.region == 'QLD1' for p in price_data_qld)
            
        finally:
            Path(temp_path).unlink()

    def test_load_invalid_format(self):
        """Test that loading an invalid format raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['invalid', 'columns', 'here'])
            writer.writeheader()
            writer.writerow({'invalid': 'data', 'columns': 'here', 'here': 'test'})
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                load_price_data(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_invalid_timestamp(self):
        """Test that invalid timestamps raise ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'region', 'price_per_kwh'])
            writer.writeheader()
            writer.writerow({
                'timestamp': 'invalid-timestamp',
                'region': 'QLD1',
                'price_per_kwh': '0.05'
            })
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError) as ctx:
                load_price_data(temp_path)
            assert 'timestamp' in str(ctx.exception).lower()
        finally:
            Path(temp_path).unlink()

    def test_load_invalid_price(self):
        """Test that invalid prices raise ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'region', 'price_per_kwh'])
            writer.writeheader()
            writer.writerow({
                'timestamp': '2026-05-01T00:00:00',
                'region': 'QLD1',
                'price_per_kwh': 'not-a-number'
            })
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError) as ctx:
                load_price_data(temp_path)
            assert 'price' in str(ctx.exception).lower()
        finally:
            Path(temp_path).unlink()

    def test_empty_csv(self):
        """Test that empty CSV raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'region', 'price_per_kwh'])
            writer.writeheader()
            # No data rows
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                load_price_data(temp_path)
        finally:
            Path(temp_path).unlink()


if __name__ == '__main__':
    unittest.main()
