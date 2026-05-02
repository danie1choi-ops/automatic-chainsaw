"""Tests for NEMOSIS loader."""

import unittest
import tempfile
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest

from src.nemosis_loader import download_dispatch_prices_nemosis, validate_date_format


class TestNEMOSISLoader(unittest.TestCase):
    """Test NEMOSIS price data downloader."""

    def test_validate_date_format_valid(self):
        """Test date format validation with valid dates."""
        self.assertTrue(validate_date_format("2024-01-01"))
        self.assertTrue(validate_date_format("2024-12-31"))
        self.assertTrue(validate_date_format("2023-02-28"))

    def test_validate_date_format_invalid(self):
        """Test date format validation with invalid dates."""
        self.assertFalse(validate_date_format("2024/01/01"))
        self.assertFalse(validate_date_format("2024-13-01"))
        self.assertFalse(validate_date_format("2024-01-32"))
        self.assertFalse(validate_date_format("not-a-date"))

    @patch('src.nemosis_loader.dynamic_data_compiler')
    def test_download_dispatch_prices_nemosis_success(self, mock_compiler):
        """Test successful NEMOSIS download."""
        # Mock NEMOSIS response
        mock_data = pd.DataFrame({
            'SETTLEMENTDATE': [
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 1, 1, 0, 5),
                datetime(2024, 1, 1, 0, 10)
            ],
            'REGIONID': ['QLD1', 'QLD1', 'QLD1'],
            'RRP': [50.0, 100.0, 200.0]
        })
        mock_compiler.return_value = mock_data

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_output.csv"

            # Run download
            download_dispatch_prices_nemosis(
                start_date="2024-01-01",
                end_date="2024-01-01",
                output_file=str(output_file)
            )

            # Verify NEMOSIS was called correctly
            mock_compiler.assert_called_once()
            call_args = mock_compiler.call_args
            self.assertEqual(call_args[0][0], '2024/01/01 00:00:00')  # start_time
            self.assertEqual(call_args[0][1], '2024/01/01 23:55:00')  # end_time
            self.assertEqual(call_args[0][2], 'DISPATCHPRICE')  # table_name
            self.assertIn('filter_cols', call_args[1])
            self.assertIn('filter_values', call_args[1])
            self.assertIn('select_columns', call_args[1])

            # Verify output file
            self.assertTrue(output_file.exists())
            df = pd.read_csv(output_file)

            # Check columns
            self.assertListEqual(list(df.columns), ['timestamp', 'region', 'price_per_kwh'])

            # Check data conversion
            self.assertEqual(len(df), 3)
            self.assertEqual(df['region'].iloc[0], 'QLD1')
            self.assertAlmostEqual(df['price_per_kwh'].iloc[0], 0.050, places=3)  # 50/1000
            self.assertAlmostEqual(df['price_per_kwh'].iloc[1], 0.100, places=3)  # 100/1000
            self.assertAlmostEqual(df['price_per_kwh'].iloc[2], 0.200, places=3)  # 200/1000

    @patch('src.nemosis_loader.dynamic_data_compiler')
    def test_download_dispatch_prices_nemosis_empty_data(self, mock_compiler):
        """Test download with empty data."""
        mock_compiler.return_value = pd.DataFrame()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_output.csv"

            with self.assertRaises(ValueError) as cm:
                download_dispatch_prices_nemosis(
                    start_date="2024-01-01",
                    end_date="2024-01-01",
                    output_file=str(output_file)
                )

            self.assertIn("No data found", str(cm.exception))

    @patch('src.nemosis_loader.dynamic_data_compiler')
    def test_download_dispatch_prices_nemosis_custom_region(self, mock_compiler):
        """Test download with custom region."""
        mock_data = pd.DataFrame({
            'SETTLEMENTDATE': [datetime(2024, 1, 1, 0, 0)],
            'REGIONID': ['NSW1'],
            'RRP': [75.0]
        })
        mock_compiler.return_value = mock_data

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_output.csv"

            download_dispatch_prices_nemosis(
                start_date="2024-01-01",
                end_date="2024-01-01",
                output_file=str(output_file),
                region="NSW1"
            )

            # Verify filter was applied for NSW1
            call_args = mock_compiler.call_args
            self.assertEqual(call_args[1]['filter_values'], (['NSW1'], [0]))

    @patch('src.nemosis_loader.dynamic_data_compiler')
    def test_download_dispatch_prices_nemosis_custom_cache_dir(self, mock_compiler):
        """Test download with custom cache directory."""
        mock_data = pd.DataFrame({
            'SETTLEMENTDATE': [datetime(2024, 1, 1, 0, 0)],
            'REGIONID': ['QLD1'],
            'RRP': [50.0]
        })
        mock_compiler.return_value = mock_data

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_output.csv"
            cache_dir = Path(temp_dir) / "custom_cache"

            download_dispatch_prices_nemosis(
                start_date="2024-01-01",
                end_date="2024-01-01",
                output_file=str(output_file),
                cache_dir=str(cache_dir)
            )

            # Verify cache directory was used
            call_args = mock_compiler.call_args
            self.assertEqual(call_args[0][3], str(cache_dir))
            
            # Verify cache directory was created
            self.assertTrue(cache_dir.exists())
            self.assertTrue(cache_dir.is_dir())

    @patch('src.nemosis_loader.dynamic_data_compiler')
    def test_download_dispatch_prices_nemosis_default_cache_dir(self, mock_compiler):
        """Test download creates default cache directory."""
        mock_data = pd.DataFrame({
            'SETTLEMENTDATE': [datetime(2024, 1, 1, 0, 0)],
            'REGIONID': ['QLD1'],
            'RRP': [50.0]
        })
        mock_compiler.return_value = mock_data

        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory so default cache is created there
            import os
            old_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                output_file = "test_output.csv"
                default_cache = Path("./data/nemosis_cache")

                download_dispatch_prices_nemosis(
                    start_date="2024-01-01",
                    end_date="2024-01-01",
                    output_file=output_file
                )

                # Verify default cache directory was created
                self.assertTrue(default_cache.exists())
                self.assertTrue(default_cache.is_dir())
                
                # Verify NEMOSIS was called with default cache path
                call_args = mock_compiler.call_args
                self.assertEqual(call_args[0][3], str(default_cache))
            finally:
                os.chdir(old_cwd)

    def test_download_dispatch_prices_nemosis_missing_nemosis(self):
        """Test error when NEMOSIS is not installed."""
        with patch('src.nemosis_loader.dynamic_data_compiler', None):
            with self.assertRaises(ImportError) as cm:
                download_dispatch_prices_nemosis(
                    start_date="2024-01-01",
                    end_date="2024-01-01",
                    output_file="dummy.csv"
                )

            self.assertIn("NEMOSIS package is required", str(cm.exception))


if __name__ == '__main__':
    unittest.main()